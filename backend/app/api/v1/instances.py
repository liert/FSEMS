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
        session, body.name, body.template_id, body.rootfs_path
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


@router.websocket("/{instance_id}/console")
async def console_ws(websocket: WebSocket, instance_id: str, token: str | None = None) -> None:
    await websocket.accept()
    try:
        await verify_ws_token(token)
    except HTTPException:
        await websocket.close(code=4401)
        return

    from app.core.database import SessionLocal

    async with SessionLocal() as session:
        try:
            instance = await get_instance(session, instance_id)
        except Exception:
            await websocket.close(code=4404)
            return
        serial_path = instance.serial_socket

    if not serial_path:
        await websocket.close(code=4400, reason="Serial socket not configured")
        return

    reader_task = None
    try:
        while not await _socket_exists(serial_path):
            await asyncio.sleep(0.2)

        reader, writer = await asyncio.open_unix_connection(serial_path)

        async def read_serial() -> None:
            try:
                while True:
                    data = await reader.read(4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except (WebSocketDisconnect, asyncio.CancelledError):
                pass

        reader_task = asyncio.create_task(read_serial())

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"]:
                writer.write(message["bytes"])
                await writer.drain()
            elif "text" in message and message["text"] == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        if reader_task:
            reader_task.cancel()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        await websocket.close(code=1000)


async def _socket_exists(path: str) -> bool:
    from pathlib import Path

    return Path(path).exists()
