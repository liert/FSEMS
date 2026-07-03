# -*- coding: utf-8 -*-
import asyncio
import logging
import re
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.instance import Instance
from app.models.snapshot import Snapshot
from app.models.task import Task
from app.services.guest_fs_offline import release_offline_mount

logger = logging.getLogger(__name__)

RUNNING_STATUSES = {"STARTING", "RUNNING", "STOPPING"}
_QEMU_PROGRESS_RE = re.compile(r"\(([\d.]+)/100%\)")


def snapshots_dir(instance_id: str) -> Path:
    return get_settings().workspace_path / instance_id / "snapshots"


def instance_drive_path(instance: Instance) -> Path:
    settings = get_settings()
    workspace = (settings.workspace_path / instance.id).resolve()
    if instance.drive_path:
        return Path(instance.drive_path)
    return workspace / "rootfs.img"


def _require_stopped(instance: Instance) -> None:
    if instance.status in RUNNING_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "INSTANCE_STATE_CONFLICT",
                "message": "Snapshot operations require a stopped instance",
            },
        )


async def _prepare_drive_access(instance_id: str) -> None:
    try:
        await release_offline_mount(instance_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_code": "OFFLINE_MOUNT_BUSY",
                "message": f"Cannot access drive while offline mount is active: {exc}",
            },
        ) from exc


async def get_snapshot(session: AsyncSession, instance_id: str, snapshot_id: str) -> Snapshot:
    result = await session.execute(
        select(Snapshot).where(Snapshot.id == snapshot_id, Snapshot.instance_id == instance_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "SNAPSHOT_NOT_FOUND", "message": "Snapshot not found"},
        )
    return snapshot


async def list_snapshots(session: AsyncSession, instance_id: str) -> list[Snapshot]:
    result = await session.execute(
        select(Snapshot)
        .where(Snapshot.instance_id == instance_id)
        .order_by(Snapshot.created_at.desc())
    )
    return list(result.scalars().all())


async def _set_task_progress(session: AsyncSession, task_id: str, progress: int, status: str | None = None) -> None:
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one()
    task.progress = progress
    if status:
        task.status = status
    await session.commit()


def parse_qemu_img_progress(line: str) -> int | None:
    """Parse ``qemu-img convert -p`` progress lines like ``(42.50/100%)``."""
    match = _QEMU_PROGRESS_RE.search(line)
    if not match:
        return None
    return min(99, int(float(match.group(1))))


async def qemu_img_convert_with_progress(
    task_id: str,
    src: Path,
    dest: Path,
    *,
    output_format: str,
    src_format: str | None = None,
    compress: bool = False,
) -> int:
    """Convert disk images via ``qemu-img convert -p`` with Task progress updates."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["qemu-img", "convert", "-p", "-O", output_format]
    if src_format:
        cmd.extend(["-f", src_format])
    if compress and output_format == "qcow2":
        cmd.append("-c")
    cmd.extend([str(src.resolve()), str(dest.resolve())])

    async with SessionLocal() as session:
        await _set_task_progress(session, task_id, 5, "RUNNING")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    last_pct = 5
    if proc.stdout:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            pct = parse_qemu_img_progress(line.decode(errors="replace"))
            if pct is not None and pct >= last_pct + 3:
                async with SessionLocal() as session:
                    await _set_task_progress(session, task_id, pct)
                last_pct = pct

    returncode = await proc.wait()
    if returncode != 0:
        if dest.is_file():
            dest.unlink(missing_ok=True)
        raise RuntimeError(f"qemu-img convert failed (exit {returncode})")
    return dest.stat().st_size if dest.is_file() else 0


async def copy_image_with_progress(task_id: str, src: Path, dest: Path) -> int:
    """复制磁盘镜像并更新 Task 进度（5–99%）。"""
    total = src.stat().st_size
    copied = 0
    chunk = 4 * 1024 * 1024
    last_reported = 0

    async with SessionLocal() as session:
        await _set_task_progress(session, task_id, 10, "RUNNING")

    with open(src, "rb") as f_in, open(dest, "wb") as f_out:
        while True:
            buf = f_in.read(chunk)
            if not buf:
                break
            f_out.write(buf)
            copied += len(buf)
            if total > 0:
                pct = min(99, int(copied * 100 / total))
                if pct >= last_reported + 5:
                    async with SessionLocal() as session:
                        await _set_task_progress(session, task_id, pct)
                    last_reported = pct

    return copied


async def snapshot_image_to_file(task_id: str, src: Path, dest: Path) -> int:
    """Write snapshot image bytes to *dest* (qcow2 convert or legacy raw copy)."""
    suffix = src.suffix.lower()
    if suffix == ".qcow2":
        return await qemu_img_convert_with_progress(
            task_id,
            src,
            dest,
            output_format="raw",
            src_format="qcow2",
        )
    return await copy_image_with_progress(task_id, src, dest)


async def create_snapshot_image(task_id: str, src: Path, dest: Path) -> int:
    """Create compressed qcow2 snapshot from instance drive."""
    return await qemu_img_convert_with_progress(
        task_id,
        src,
        dest,
        output_format="qcow2",
        src_format="raw",
        compress=True,
    )


async def queue_create_snapshot(session: AsyncSession, instance: Instance, name: str) -> tuple[str, str]:
    _require_stopped(instance)
    await _prepare_drive_access(instance.id)

    drive = instance_drive_path(instance)
    if not drive.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": f"Drive image not found: {drive}"},
        )

    snapshot_id = f"snap_{uuid.uuid4()}"
    dest_dir = snapshots_dir(instance.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{snapshot_id}.qcow2"

    task_id = f"task_{uuid.uuid4()}"
    task = Task(
        id=task_id,
        instance_id=instance.id,
        task_type="SNAPSHOT_CREATE",
        status="PENDING",
        progress=0,
        result_ref=snapshot_id,
    )
    session.add(task)
    await session.commit()

    from app.tasks.snapshot_ops import run_snapshot_create

    run_snapshot_create.delay(
        task_id,
        instance.id,
        str(drive),
        str(dest),
        name.strip(),
        snapshot_id,
    )
    return task_id, snapshot_id


async def queue_restore_snapshot(
    session: AsyncSession, instance: Instance, snapshot_id: str
) -> str:
    _require_stopped(instance)
    await _prepare_drive_access(instance.id)

    snapshot = await get_snapshot(session, instance.id, snapshot_id)
    image = Path(snapshot.image_path)
    if not image.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "SNAPSHOT_NOT_FOUND", "message": "Snapshot image file missing on disk"},
        )

    drive = instance_drive_path(instance)
    task_id = f"task_{uuid.uuid4()}"
    task = Task(
        id=task_id,
        instance_id=instance.id,
        task_type="SNAPSHOT_RESTORE",
        status="PENDING",
        progress=0,
        result_ref=snapshot_id,
    )
    session.add(task)
    await session.commit()

    from app.tasks.snapshot_ops import run_snapshot_restore

    run_snapshot_restore.delay(task_id, instance.id, str(image), str(drive), snapshot_id)
    return task_id


async def delete_snapshot(session: AsyncSession, instance_id: str, snapshot_id: str) -> None:
    snapshot = await get_snapshot(session, instance_id, snapshot_id)
    image = Path(snapshot.image_path)
    if image.is_file():
        await asyncio.to_thread(image.unlink)
    await session.delete(snapshot)
    await session.commit()


async def delete_all_snapshots(instance_id: str) -> None:
    snap_dir = snapshots_dir(instance_id)
    if snap_dir.is_dir():
        await asyncio.to_thread(shutil.rmtree, snap_dir, True)
