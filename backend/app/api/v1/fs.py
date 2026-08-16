# -*- coding: utf-8 -*-
import logging
import shutil

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status,
    UploadFile,
    File,
    Form,
    WebSocket,
)
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis
import hashlib
import json
import uuid
from pathlib import Path
from starlette.websockets import WebSocketDisconnect

from app.api.deps import get_current_user, get_db, verify_ws_token
from app.schemas.common import ApiResponse
from app.schemas.fs import (
    FileEntry,
    HostDirListing,
    GuestDirListing,
    TransferRequest,
    TransferResponse,
    HostUploadResult,
    GuestFsOpRequest,
    GuestFsOpResult,
    HostFsOpRequest,
    HostFsOpResult,
)
from app.services.host_fs import (
    list_directory,
    resolve_instance_host_root,
    resolve_workspace_entry,
    resolve_workspace_path,
    resolve_host_directory,
    host_mkdir,
    host_remove,
    host_rename,
)
from app.services.instance_service import get_instance
from app.services.guest_fs_offline import list_guest_offline_directory
from app.services.ssh_service import (
    GuestPathNotFoundError,
    list_guest_directory,
    guest_mkdir,
    guest_remove,
    guest_rename,
    normalize_guest_path,
)
from app.core.config import get_settings
from app.models.task import Task
from app.services.host_shell import run_host_shell_session
from app.tasks.file_transfer import run_file_transfer

router = APIRouter(prefix="/fs", tags=["fs"])
logger = logging.getLogger(__name__)

RUNNING_STATUSES = {"STARTING", "RUNNING", "STOPPING"}


async def get_redis_client():
    settings = get_settings()
    return aioredis.from_url(settings.REDIS_URL, decode_responses=True)


def _instance_drive_path(instance) -> Path:
    settings = get_settings()
    workspace = (settings.workspace_path / instance.id).resolve()
    if instance.drive_path:
        return Path(instance.drive_path).resolve()
    return (workspace / "rootfs.img").resolve()


@router.get("/host", response_model=ApiResponse[HostDirListing])
async def list_host_dir(
    path: str = Query(""),
    instance_id: str | None = Query(None),
    _user: str = Depends(get_current_user),
) -> ApiResponse[HostDirListing]:
    host_root_path: str | None = None

    if instance_id:
        host_root_path = resolve_instance_host_root(instance_id).as_posix()

    if not path and instance_id and host_root_path:
        target = Path(host_root_path)
    else:
        target = resolve_host_directory(path, instance_id)
    files = [FileEntry(**entry) for entry in list_directory(target)]
    return ApiResponse(
        data=HostDirListing(
            current_path=target.as_posix(),
            files=files,
            host_root_path=host_root_path,
        ),
        message="Host directory listed",
    )


@router.post("/host/ops", response_model=ApiResponse[HostFsOpResult])
async def host_fs_op(
    req: HostFsOpRequest,
    _user: str = Depends(get_current_user),
) -> ApiResponse[HostFsOpResult]:
    if req.op not in ("mkdir", "delete", "rename"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_HOST_OP", "message": "op must be mkdir, delete, or rename"},
        )

    if req.op == "mkdir":
        target = host_mkdir(req.path)
        return ApiResponse(
            data=HostFsOpResult(op=req.op, path=target.as_posix()),
            message="Host directory created",
        )

    if req.op == "delete":
        target = host_remove(req.path)
        return ApiResponse(
            data=HostFsOpResult(op=req.op, path=target.as_posix()),
            message="Host path deleted",
        )

    if not req.dest_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_HOST_OP", "message": "dest_path required for rename"},
        )
    dest = host_rename(req.path, req.dest_path)
    return ApiResponse(
        data=HostFsOpResult(op=req.op, path=req.path, dest_path=dest.as_posix()),
        message="Host path renamed",
    )


async def _read_guest_cache(cache_key: str) -> list[FileEntry] | None:
    r = await get_redis_client()
    try:
        cached_data = await r.get(cache_key)
        if cached_data:
            files_dict = json.loads(cached_data)
            return [FileEntry(**f) for f in files_dict]
    except Exception:
        pass
    finally:
        await r.close()
    return None


async def _write_guest_cache(cache_key: str, files: list[dict]) -> None:
    r = await get_redis_client()
    try:
        await r.setex(cache_key, 10, json.dumps(files))
    except Exception:
        pass
    finally:
        await r.close()


async def _invalidate_guest_cache(instance_id: str, path: str) -> None:
    import posixpath

    parent = posixpath.dirname(path.rstrip("/")) or "/"
    path_hash = hashlib.sha256(parent.encode()).hexdigest()
    r = await get_redis_client()
    try:
        await r.delete(f"fsems:fs_cache:online:{instance_id}:{path_hash}")
        await r.delete(f"fsems:fs_cache:offline:{instance_id}:{path_hash}")
    except Exception:
        pass
    finally:
        await r.close()


@router.get("/guest/{instance_id}", response_model=ApiResponse[GuestDirListing])
async def list_guest_dir(
    instance_id: str,
    path: str = Query("/"),
    mode: str = Query("online"),
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[GuestDirListing]:
    if mode not in ("online", "offline"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_VFS_MODE", "message": "mode must be online or offline"},
        )

    instance = await get_instance(session, instance_id)

    if mode == "online":
        if instance.status != "RUNNING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "INSTANCE_STATE_CONFLICT",
                    "message": "Online guest VFS requires a running instance; use mode=offline when stopped",
                },
            )
        return await _list_guest_online(instance, instance_id, path)

    if instance.status in RUNNING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "INSTANCE_STATE_CONFLICT",
                "message": "Offline guest VFS requires a stopped instance; unmount before start",
            },
        )

    return await _list_guest_offline(instance, instance_id, path)


@router.post("/guest/{instance_id}/ops", response_model=ApiResponse[GuestFsOpResult])
async def guest_fs_op(
    instance_id: str,
    req: GuestFsOpRequest,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[GuestFsOpResult]:
    if req.op not in ("mkdir", "delete", "rename"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_GUEST_OP", "message": "op must be mkdir, delete, or rename"},
        )

    instance = await get_instance(session, instance_id)
    if instance.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "INSTANCE_STATE_CONFLICT",
                "message": "Guest file operations require a running instance",
            },
        )

    host = instance.guest_ssh_host
    template = instance.template
    port = template.guest_ssh_port if template else 22

    try:
        if req.op == "mkdir":
            await guest_mkdir(host, port, req.path)
            await _invalidate_guest_cache(instance_id, req.path)
            return ApiResponse(
                data=GuestFsOpResult(op=req.op, path=normalize_guest_path(req.path)),
                message="Guest directory created",
            )
        if req.op == "delete":
            await guest_remove(host, port, req.path)
            await _invalidate_guest_cache(instance_id, req.path)
            return ApiResponse(
                data=GuestFsOpResult(op=req.op, path=normalize_guest_path(req.path)),
                message="Guest path deleted",
            )
        if not req.dest_path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "INVALID_GUEST_OP", "message": "dest_path required for rename"},
            )
        await guest_rename(host, port, req.path, req.dest_path)
        await _invalidate_guest_cache(instance_id, req.path)
        await _invalidate_guest_cache(instance_id, req.dest_path)
        return ApiResponse(
            data=GuestFsOpResult(
                op=req.op,
                path=normalize_guest_path(req.path),
                dest_path=normalize_guest_path(req.dest_path),
            ),
            message="Guest path renamed",
        )
    except GuestPathNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": e.message},
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Guest fs op failed instance=%s op=%s path=%s", instance_id, req.op, req.path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "GUEST_FS_OP_FAILED", "message": str(e)},
        ) from e


async def _list_guest_online(instance, instance_id: str, path: str) -> ApiResponse[GuestDirListing]:
    host = instance.guest_ssh_host
    template = instance.template
    port = template.guest_ssh_port if template else 22

    path_hash = hashlib.sha256(path.encode()).hexdigest()
    cache_key = f"fsems:fs_cache:online:{instance_id}:{path_hash}"

    cached = await _read_guest_cache(cache_key)
    if cached is not None:
        return ApiResponse(
            data=GuestDirListing(
                instance_id=instance_id,
                current_path=path,
                files=cached,
                mode="online",
            ),
            message="Guest directory listed (Cached)",
        )

    try:
        guest_files = await list_guest_directory(host, port, path)
    except GuestPathNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": e.message},
        ) from e
    except Exception as e:
        logger.exception("Guest directory listing failed for %s:%s path=%s", host, port, path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SSH_CONNECT_FAILED", "message": f"SSH operation failed: {e}"},
        ) from e

    await _write_guest_cache(cache_key, guest_files)
    files = [FileEntry(**f) for f in guest_files]
    return ApiResponse(
        data=GuestDirListing(instance_id=instance_id, current_path=path, files=files, mode="online"),
        message="Guest directory listed",
    )


async def _list_guest_offline(instance, instance_id: str, path: str) -> ApiResponse[GuestDirListing]:
    drive_path = _instance_drive_path(instance)
    if not drive_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": f"Drive image not found: {drive_path}"},
        )

    path_hash = hashlib.sha256(path.encode()).hexdigest()
    cache_key = f"fsems:fs_cache:offline:{instance_id}:{path_hash}"

    cached = await _read_guest_cache(cache_key)
    if cached is not None:
        return ApiResponse(
            data=GuestDirListing(
                instance_id=instance_id,
                current_path=path,
                files=cached,
                mode="offline",
            ),
            message="Guest directory listed offline (Cached)",
        )

    try:
        guest_files = await list_guest_offline_directory(instance_id, drive_path, path)
    except GuestPathNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": e.message},
        ) from e
    except Exception as e:
        logger.exception("Offline guest listing failed instance=%s path=%s", instance_id, path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "OFFLINE_MOUNT_FAILED", "message": f"Offline VFS failed: {e}"},
        ) from e

    await _write_guest_cache(cache_key, guest_files)
    files = [FileEntry(**f) for f in guest_files]
    return ApiResponse(
        data=GuestDirListing(instance_id=instance_id, current_path=path, files=files, mode="offline"),
        message="Guest directory listed offline",
    )


@router.post("/transfer", response_model=ApiResponse[TransferResponse], status_code=status.HTTP_202_ACCEPTED)
async def transfer_file(
    req: TransferRequest,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[TransferResponse]:
    instance = await get_instance(session, req.instance_id)
    if instance.status != "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "INSTANCE_STATE_CONFLICT", "message": "Instance is not running"},
        )

    host_path = req.src if req.direction == "host_to_guest" else req.dest
    path_obj = Path(host_path)
    try:
        if req.direction == "host_to_guest":
            # 保留源路径最后一个分量的符号链接，让 iot-tools 同时复制链接和真实目标。
            resolved = resolve_workspace_entry(host_path)
            if not resolved.is_file() and not resolved.is_dir():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Source host path is not a file or directory"},
                )
            req.src = str(resolved)
        elif req.direction == "guest_to_host":
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

    task_id = f"task_{uuid.uuid4()}"
    task = Task(
        id=task_id,
        instance_id=req.instance_id,
        task_type="FILE_TRANSFER",
        status="PENDING",
        progress=0,
    )
    session.add(task)
    await session.commit()

    run_file_transfer.delay(task_id, req.direction, req.src, req.dest)

    return ApiResponse(
        data=TransferResponse(task_id=task_id),
        message="Transfer task queued",
    )


def _resolve_instance_rootfs_shell_cwd(instance_id: str) -> Path:
    """
    宿主机 shell 工作目录：优先实例自定义 RootFS 解压目录 workspace/<id>/rootfs，
    不存在则回退到实例 workspace；再不行用全局 workspace。
    """
    settings = get_settings()
    ws = settings.workspace_path.resolve()
    inst_ws = (ws / instance_id).resolve()
    rootfs_dir = (inst_ws / "rootfs").resolve()
    try:
        # 防止 instance_id 含 .. 逃出 workspace
        inst_ws.relative_to(ws)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid instance_id",
        ) from exc

    if rootfs_dir.is_dir():
        return rootfs_dir
    if inst_ws.is_dir():
        return inst_ws
    return ws


@router.websocket("/host-shell")
async def host_shell_ws(
    websocket: WebSocket,
    token: str | None = None,
    instance_id: str | None = None,
) -> None:
    """
    宿主机交互式 shell WebSocket。
    工作目录为实例「自定义 RootFS」解压目录（workspace/<id>/rootfs），
    而非宿主机 /。协议与访客串口一致：二进制输入/输出，JSON resize。
    """
    await websocket.accept()
    try:
        await verify_ws_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    if not instance_id or not instance_id.strip():
        try:
            await websocket.send_bytes(
                "\r\n\x1b[31m[FSEMS] 缺少 instance_id\x1b[0m\r\n".encode()
            )
            await websocket.close(code=4400)
        except Exception:
            pass
        return

    try:
        workdir = str(_resolve_instance_rootfs_shell_cwd(instance_id.strip()))
    except HTTPException:
        try:
            await websocket.close(code=4400)
        except Exception:
            pass
        return

    try:
        await websocket.send_bytes(
            f"\r\n\x1b[90m[FSEMS] 自定义 RootFS 目录 shell · cwd={workdir}\x1b[0m\r\n".encode()
        )
        await run_host_shell_session(websocket, cwd=workdir, cols=80, rows=24)
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.exception("host shell session error: %s", exc)
        try:
            await websocket.send_bytes(
                f"\r\n\x1b[31m[FSEMS] 宿主机 shell 异常: {exc}\x1b[0m\r\n".encode()
            )
            await websocket.close(code=1011)
        except Exception:
            pass


@router.post("/host/upload", response_model=ApiResponse[HostUploadResult])
async def upload_to_host(
    file: UploadFile = File(...),
    path: str = Form(""),
    instance_id: str | None = Form(None),
    _user: str = Depends(get_current_user),
) -> ApiResponse[HostUploadResult]:
    target_dir = resolve_host_directory(path, instance_id)
    raw_name = (file.filename or "upload").strip()
    filename = Path(raw_name).name
    if not filename or filename in (".", "..") or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_FILENAME", "message": "Invalid upload filename"},
        )

    dest = (target_dir / filename).resolve()
    try:
        dest.relative_to(get_settings().workspace_path.resolve())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Upload path outside workspace"},
        ) from exc

    try:
        with dest.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except OSError as exc:
        logger.exception("Host upload failed path=%s", dest)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "UPLOAD_FAILED", "message": f"Failed to write file: {exc}"},
        ) from exc
    finally:
        await file.close()

    size = dest.stat().st_size
    return ApiResponse(
        data=HostUploadResult(path=str(dest), name=filename, size=size),
        message="File uploaded",
    )
