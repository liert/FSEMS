import asyncio
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, verify_ws_token
from app.schemas.common import ApiResponse
from app.schemas.instance import (
    InstanceAction,
    InstanceActionResult,
    InstanceCreate,
    InstanceCreated,
    InstanceListOut,
    InstanceOut,
)
from app.services import instance_service
from app.services.instance_service import get_instance, instance_to_out

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
    updated = await instance_service.perform_action(session, instance, body.action)
    return ApiResponse(
        data=InstanceActionResult(id=updated.id, status=updated.status),
        message=f"Action '{body.action}' initiated",
    )


@router.get("/{instance_id}", response_model=ApiResponse[InstanceOut])
async def get_instance_detail(
    instance_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[InstanceOut]:
    instance = await get_instance(session, instance_id)
    return ApiResponse(
        data=InstanceOut(**instance_to_out(instance)),
        message="Instance details fetched",
    )


@router.delete("/{instance_id}", response_model=ApiResponse[dict])
async def delete_instance(
    instance_id: str,
    _user: str = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ApiResponse[dict]:
    await instance_service.delete_instance(session, instance_id)
    return ApiResponse(data={}, message="Instance deleted successfully")


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
                cb.write_bytes(message["bytes"])
            elif "text" in message and message["text"] == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        cb.websockets.discard(websocket)
