import asyncio
import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, verify_ws_token
from app.schemas.common import ApiResponse
from app.schemas.instance import (
    InstanceAction,
    InstanceActionResult,
    InstanceCreate,
    InstanceCreated,
    InstanceDetailOut,
    InstanceListOut,
    InstanceOut,
    DriveExpandRequest,
    DriveExpandResult,
    CustomRootfsUpdate,
)
from app.schemas.snapshot import SnapshotCreate, SnapshotListOut, SnapshotOut, SnapshotTaskResponse
from app.services import instance_service, snapshot_service
from app.services.instance_service import get_instance, instance_detail_to_out, instance_to_out

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/instances", tags=["instances"])


@router.get("", response_model=ApiResponse[InstanceListOut])
async def list_instances(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[InstanceListOut]:
    total, items = await instance_service.list_instances(session, page, limit)
    return ApiResponse(
        data=InstanceListOut(
            total=total,
            list=[InstanceOut(**instance_to_out(i)) for i in items],
        ),
        message="Instances fetched",
    )


@router.post("", response_model=ApiResponse[InstanceCreated], status_code=201)
async def create_instance(
    body: InstanceCreate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[InstanceCreated]:
    instance = await instance_service.create_instance(
        session, body.name, body.template_id, body.rootfs_path, body.network_type
    )
    return ApiResponse(
        data=InstanceCreated(id=instance.id, status=instance.status),
        message="Instance created successfully",
    )


@router.post("/{instance_id}/action", response_model=ApiResponse[InstanceActionResult])
async def instance_action(
    instance_id: str,
    body: InstanceAction,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[InstanceActionResult]:
    instance = await get_instance(session, instance_id)
    allow_sigkill = True if body.allow_sigkill is None else body.allow_sigkill
    updated = await instance_service.perform_action(
        session, instance, body.action, allow_sigkill=allow_sigkill
    )
    return ApiResponse(
        data=InstanceActionResult(id=updated.id, status=updated.status),
        message=f"Action '{body.action}' initiated",
    )


@router.get("/{instance_id}", response_model=ApiResponse[InstanceDetailOut])
async def get_instance_detail(
    instance_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[InstanceDetailOut]:
    instance = await get_instance(session, instance_id)
    return ApiResponse(
        data=InstanceDetailOut(**instance_detail_to_out(instance)),
        message="Instance details fetched",
    )


@router.post("/{instance_id}/drive/expand", response_model=ApiResponse[DriveExpandResult])
async def expand_instance_drive(
    instance_id: str,
    body: DriveExpandRequest,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[DriveExpandResult]:
    instance = await get_instance(session, instance_id)
    result = await instance_service.expand_instance_drive(
        session, instance, body.expand_mb, body.manage_lifecycle
    )
    return ApiResponse(data=DriveExpandResult(**result), message="Drive expanded")


@router.put("/{instance_id}/custom-rootfs", response_model=ApiResponse[InstanceDetailOut])
async def update_custom_rootfs(
    instance_id: str,
    body: CustomRootfsUpdate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[InstanceDetailOut]:
    """创建后修改自定义 RootFS 源路径并重新解压/拷贝到实例 workspace/rootfs。"""
    instance = await get_instance(session, instance_id)
    updated = await instance_service.update_custom_rootfs(session, instance, body.rootfs_path)
    return ApiResponse(
        data=InstanceDetailOut(**instance_detail_to_out(updated)),
        message="Custom RootFS updated",
    )


@router.delete("/{instance_id}", response_model=ApiResponse[dict])
async def delete_instance(
    instance_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await instance_service.delete_instance(session, instance_id)
    return ApiResponse(data={}, message="Instance deleted successfully")


@router.get("/{instance_id}/snapshots", response_model=ApiResponse[SnapshotListOut])
async def list_instance_snapshots(
    instance_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotListOut]:
    await get_instance(session, instance_id)
    items = await snapshot_service.list_snapshots(session, instance_id)
    return ApiResponse(
        data=SnapshotListOut(list=[SnapshotOut.model_validate(s) for s in items]),
        message="Snapshots fetched",
    )


@router.post(
    "/{instance_id}/snapshots",
    response_model=ApiResponse[SnapshotTaskResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_instance_snapshot(
    instance_id: str,
    body: SnapshotCreate,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotTaskResponse]:
    instance = await get_instance(session, instance_id)
    task_id, snapshot_id = await snapshot_service.queue_create_snapshot(session, instance, body.name)
    return ApiResponse(
        data=SnapshotTaskResponse(task_id=task_id, snapshot_id=snapshot_id),
        message="Snapshot create task queued",
    )


@router.post(
    "/{instance_id}/snapshots/{snapshot_id}/restore",
    response_model=ApiResponse[SnapshotTaskResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def restore_instance_snapshot(
    instance_id: str,
    snapshot_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[SnapshotTaskResponse]:
    instance = await get_instance(session, instance_id)
    task_id = await snapshot_service.queue_restore_snapshot(session, instance, snapshot_id)
    return ApiResponse(
        data=SnapshotTaskResponse(task_id=task_id, snapshot_id=snapshot_id),
        message="Snapshot restore task queued",
    )


@router.delete("/{instance_id}/snapshots/{snapshot_id}", response_model=ApiResponse[dict])
async def delete_instance_snapshot(
    instance_id: str,
    snapshot_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await get_instance(session, instance_id)
    await snapshot_service.delete_snapshot(session, instance_id, snapshot_id)
    return ApiResponse(data={}, message="Snapshot deleted")


@router.websocket("/{instance_id}/console")
async def console_ws(websocket: WebSocket, instance_id: str, token: str | None = None) -> None:
    await websocket.accept()
    try:
        await verify_ws_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    from app.services import qemu_manager

    try:
        # 1. 获取或自动建立该实例的串口背景读取器
        cb = qemu_manager.ensure_console_reader(instance_id)
    except Exception as e:
        logger.error(f"无法初始化串口监听: {e}")
        await websocket.close(code=4404, reason="Console initialization failed")
        return

    # 2. 发送已保存的历史输出，默认最大 1000 行
    history = b"".join(list(cb.lines))
    if cb.current_line:
        history += bytes(cb.current_line)
    if history:
        await websocket.send_bytes(history)

    # 3. 将当前 websocket 追加到广播列表
    cb.websockets.add(websocket)

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"]:
                # 终端键盘输入必须用二进制帧写入串口
                cb.write_bytes(message["bytes"])
            elif "text" in message and message["text"] is not None:
                text = message["text"]
                if text == "ping":
                    await websocket.send_text("pong")
                    continue
                # 控制帧：resize 等 JSON
                if text.startswith("{") and text.endswith("}"):
                    try:
                        payload = json.loads(text)
                        if payload.get("type") == "resize":
                            cb.write_resize(payload.get("cols", 80), payload.get("rows", 24))
                            continue
                    except (json.JSONDecodeError, TypeError, ValueError):
                        pass
                # 兼容旧客户端：纯文本输入也写入串口
                cb.write_bytes(text.encode("utf-8", errors="replace"))
    except WebSocketDisconnect:
        pass
    finally:
        cb.websockets.discard(websocket)
