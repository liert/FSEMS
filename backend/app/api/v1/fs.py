# -*- coding: utf-8 -*-
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import hashlib
import json
import uuid
from pathlib import Path

from app.api.deps import get_current_user, get_db
from app.schemas.common import ApiResponse
from app.schemas.fs import (
    FileEntry, 
    HostDirListing, 
    GuestDirListing, 
    TransferRequest, 
    TransferResponse
)
from app.services.host_fs import list_directory, resolve_workspace_path
from app.services.instance_service import get_instance
from app.services.ssh_service import list_guest_directory
from app.core.config import get_settings
from app.models.task import Task
from app.tasks.file_transfer import run_file_transfer

router = APIRouter(prefix="/fs", tags=["fs"])

async def get_redis_client():
    """
    获取 Redis 客户端，用于缓存目录树。
    """
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)

@router.get("/host", response_model=ApiResponse[HostDirListing])
async def list_host_dir(
    path: str = Query(""),
    instance_id: str | None = Query(None),
    _user: str = Depends(get_current_user),
) -> ApiResponse[HostDirListing]:
    """
    浏览宿主机指定工作目录的文件列表。
    """
    settings = get_settings()
    # 如果 path 为空且提供了 instance_id，自动定位到该实例专属解压目录（如存在）
    if not path and instance_id:
        inst_dir = Path(settings.FSEMS_WORKSPACE) / instance_id
        if inst_dir.exists() and inst_dir.is_dir():
            target = inst_dir
        else:
            target = resolve_workspace_path(path)
    else:
        target = resolve_workspace_path(path)

    if not target.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Not a directory"},
        )
    files = [FileEntry(**entry) for entry in list_directory(target)]
    return ApiResponse(
        data=HostDirListing(current_path=target.as_posix(), files=files),
        message="Host directory listed",
    )

@router.get("/guest/{instance_id}", response_model=ApiResponse[GuestDirListing])
async def list_guest_dir(
    instance_id: str,
    path: str = Query("/"),
    mode: str = Query("online"),
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[GuestDirListing]:
    """
    浏览访客机 (QEMU 虚拟机) 指定目录的文件列表，支持 10 秒 Redis 短暂缓存。
    """
    if mode != "online":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "SSH_CONNECT_FAILED", "message": "Only online mode is supported in Phase 2"},
        )
        
    instance = await get_instance(session, instance_id)
    if instance.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "INSTANCE_STATE_CONFLICT", "message": "Instance is not running"},
        )
        
    host = instance.guest_ssh_host
    template = instance.template
    port = template.guest_ssh_port if template else 22
    
    # 生成缓存 key
    path_hash = hashlib.sha256(path.encode()).hexdigest()
    cache_key = f"fsems:fs_cache:{instance_id}:{path_hash}"
    
    # 尝试从 Redis 缓存获取
    r = await get_redis_client()
    try:
        cached_data = await r.get(cache_key)
        if cached_data:
            files_dict = json.loads(cached_data)
            files = [FileEntry(**f) for f in files_dict]
            return ApiResponse(
                data=GuestDirListing(instance_id=instance_id, current_path=path, files=files),
                message="Guest directory listed (Cached)",
            )
    except Exception:
        pass
    finally:
        await r.close()
        
    # 未命中缓存，发起 SSH 抓取
    try:
        guest_files = await list_guest_directory(host, port, path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SSH_CONNECT_FAILED", "message": f"SSH operation failed: {e}"},
        )
        
    # 将数据写入 Redis 缓存，TTL = 10s
    r = await get_redis_client()
    try:
        await r.setex(cache_key, 10, json.dumps(guest_files))
    except Exception:
        pass
    finally:
        await r.close()
        
    files = [FileEntry(**f) for f in guest_files]
    return ApiResponse(
        data=GuestDirListing(instance_id=instance_id, current_path=path, files=files),
        message="Guest directory listed",
    )

@router.post("/transfer", response_model=ApiResponse[TransferResponse], status_code=status.HTTP_202_ACCEPTED)
async def transfer_file(
    req: TransferRequest,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TransferResponse]:
    """
    发起文件双向传输任务 (宿主机 <-> 访客机)，触发异步 Celery 任务。
    """
    instance = await get_instance(session, req.instance_id)
    if instance.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "INSTANCE_STATE_CONFLICT", "message": "Instance is not running"},
        )
        
    # 宿主机路径的安全性及规范化校验
    host_path = req.src if req.direction == "host_to_guest" else req.dest
    path_obj = Path(host_path)
    try:
        if req.direction == "host_to_guest":
            # 必须为工作空间内存在的物理文件
            resolved = resolve_workspace_path(host_path)
            if not resolved.is_file():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Source host path is not a file"},
                )
            req.src = str(resolved)
        elif req.direction == "guest_to_host":
            # 目的文件虽然尚未创建，但其所在的父目录必须处于工作空间内
            parent_dir = str(path_obj.parent)
            resolved_parent = resolve_workspace_path(parent_dir)
            req.dest = str(resolved_parent / path_obj.name)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "TRANSFER_EXECUTION_ERROR", "message": "Invalid transfer direction"},
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": f"Invalid host path: {e}"},
        )
        
    # 写入 SQLite 数据库以初始化任务
    task_id = f"task_{uuid.uuid4()}"
    task = Task(
        id=task_id,
        instance_id=req.instance_id,
        task_type="FILE_TRANSFER",
        status="PENDING",
        progress=0
    )
    session.add(task)
    await session.commit()
    
    # 唤醒异步 Celery 任务进行传输
    run_file_transfer.delay(task_id, req.direction, req.src, req.dest)
    
    return ApiResponse(
        data=TransferResponse(task_id=task_id),
        message="Transfer task queued",
    )
