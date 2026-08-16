# -*- coding: utf-8 -*-
"""MCP 工具实现：直接调用 FSEMS 服务层。"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.template import Template
from app.services import instance_service, snapshot_service
from app.services.instance_service import instance_detail_to_out, instance_to_out


def _err(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return {
                "ok": False,
                "http_status": exc.status_code,
                "error_code": detail.get("error_code"),
                "error": detail.get("message") or detail.get("error_code") or str(detail),
                "details": detail,
            }
        return {"ok": False, "http_status": exc.status_code, "error": str(detail)}
    return {"ok": False, "error_code": type(exc).__name__, "error": str(exc)}


async def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "ok": True,
        "service": "FSEMS",
        "workspace": str(settings.workspace_path),
        "kernels_dir": str(settings.kernels_path),
        "rootfs_dir": str(settings.rootfs_path),
        "database": settings.DATABASE_URL.split("///")[-1] if "///" in settings.DATABASE_URL else settings.DATABASE_URL,
        "mcp": {
            "enabled": settings.MCP_ENABLED,
            "path": settings.MCP_PATH,
            "stateless": settings.MCP_STATELESS,
        },
    }


async def list_templates(arch: str | None = None) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            q = select(Template).order_by(Template.id)
            if arch:
                q = q.where(Template.arch == arch)
            result = await session.execute(q)
            rows = result.scalars().all()
            return {
                "ok": True,
                "total": len(rows),
                "templates": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "arch": t.arch,
                        "qemu_binary": t.qemu_binary,
                        "machine": t.machine,
                        "cpu": t.cpu,
                        "effective_cpu": instance_service.qemu_manager.effective_cpu(t),
                        "ram_size": t.ram_size,
                        "kernel_path": t.kernel_path,
                        "drive_path": t.drive_path,
                        "kernel_append": t.kernel_append,
                        "effective_kernel_append": instance_service.qemu_manager.effective_kernel_append(t),
                        "block_device": instance_service.qemu_manager.block_device_arg(t.machine) or "ide",
                        "network_device": instance_service.qemu_manager.net_device_arg(t.machine),
                        "extra_args": t.extra_args,
                        "guest_ssh_host": t.guest_ssh_host,
                        "guest_ssh_port": t.guest_ssh_port,
                    }
                    for t in rows
                ],
            }
    except Exception as exc:
        return _err(exc)


async def list_instances(page: int = 1, limit: int = 20) -> dict[str, Any]:
    try:
        page = max(1, int(page))
        limit = min(100, max(1, int(limit)))
        async with SessionLocal() as session:
            total, items = await instance_service.list_instances(session, page, limit)
            return {
                "ok": True,
                "total": total,
                "page": page,
                "limit": limit,
                "instances": [instance_to_out(i) for i in items],
            }
    except Exception as exc:
        return _err(exc)


async def get_instance(instance_id: str) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            inst = await instance_service.get_instance(session, instance_id)
            return {"ok": True, "instance": instance_detail_to_out(inst)}
    except Exception as exc:
        return _err(exc)


async def create_instance(
    name: str,
    template_id: int,
    rootfs_path: str | None = None,
    network_type: str = "same",
    filesystem_type: str = "ext4",
    use_custom_rootfs: bool = False,
) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            inst = await instance_service.create_instance(
                session,
                name=name,
                template_id=int(template_id),
                rootfs_path=rootfs_path,
                network_type=network_type or "same",
                filesystem_type=filesystem_type or "ext4",
                use_custom_rootfs=use_custom_rootfs,
            )
            return {
                "ok": True,
                "id": inst.id,
                "status": inst.status,
                "guest_ssh_host": inst.guest_ssh_host,
                "filesystem_type": inst.filesystem_type,
                "use_custom_rootfs": bool(inst.use_custom_rootfs),
                "message": "Instance created",
            }
    except Exception as exc:
        return _err(exc)


async def instance_diagnostics(instance_id: str, serial_lines: int = 200) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            inst = await instance_service.get_instance(session, instance_id)
            diagnostics = await instance_service.qemu_manager.instance_diagnostics(
                inst,
                inst.template,
                serial_lines=max(0, min(int(serial_lines), 2000)),
            )
            return {"ok": True, "diagnostics": diagnostics}
    except Exception as exc:
        return _err(exc)


async def instance_action(
    instance_id: str,
    action: str,
    allow_sigkill: bool = True,
    wait_boot: bool = False,
) -> dict[str, Any]:
    action = (action or "").strip().lower()
    if action not in {"start", "stop", "reset"}:
        return {"ok": False, "error": "action 必须是 start / stop / reset"}
    try:
        async with SessionLocal() as session:
            inst = await instance_service.get_instance(session, instance_id)
            updated = await instance_service.perform_action(
                session,
                inst,
                action,
                allow_sigkill=allow_sigkill,
                wait_boot=wait_boot,
            )
            diagnostics = await instance_service.qemu_manager.instance_diagnostics(
                updated, updated.template, serial_lines=80
            )
            return {
                "ok": True,
                "id": updated.id,
                "status": updated.status,
                "action": action,
                "diagnostics": diagnostics,
            }
    except Exception as exc:
        return _err(exc)


async def delete_instance(instance_id: str) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            await instance_service.delete_instance(session, instance_id)
            return {"ok": True, "id": instance_id, "message": "Instance deleted"}
    except Exception as exc:
        return _err(exc)


async def update_custom_rootfs(instance_id: str, rootfs_path: str | None = None) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            inst = await instance_service.get_instance(session, instance_id)
            updated = await instance_service.update_custom_rootfs(session, inst, rootfs_path)
            return {"ok": True, "instance": instance_detail_to_out(updated)}
    except Exception as exc:
        return _err(exc)


async def list_snapshots(instance_id: str) -> dict[str, Any]:
    try:
        async with SessionLocal() as session:
            await instance_service.get_instance(session, instance_id)
            items = await snapshot_service.list_snapshots(session, instance_id)
            return {
                "ok": True,
                "instance_id": instance_id,
                "snapshots": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "image_path": s.image_path,
                        "size_bytes": s.size_bytes,
                        "created_at": s.created_at,
                    }
                    for s in items
                ],
            }
    except Exception as exc:
        return _err(exc)
