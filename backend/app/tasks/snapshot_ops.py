# -*- coding: utf-8 -*-
import asyncio
import logging
from pathlib import Path

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.snapshot import Snapshot
from app.models.task import Task
from app.services.snapshot_service import (
    create_snapshot_image,
    snapshot_image_to_file,
)

logger = logging.getLogger(__name__)


async def _mark_task_failure(task_id: str, message: str) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        task.status = "FAILURE"
        task.progress = 100
        task.error_msg = message
        await session.commit()


async def async_snapshot_create(
    task_id: str,
    instance_id: str,
    src: str,
    dest: str,
    name: str,
    snapshot_id: str,
) -> None:
    src_path = Path(src)
    dest_path = Path(dest)
    try:
        size_bytes = await create_snapshot_image(task_id, src_path, dest_path)
        async with SessionLocal() as session:
            session.add(
                Snapshot(
                    id=snapshot_id,
                    instance_id=instance_id,
                    name=name,
                    image_path=str(dest_path),
                    size_bytes=size_bytes,
                )
            )
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "SUCCESS"
            task.progress = 100
            await session.commit()
        logger.info("快照创建任务 %s 完成 snapshot=%s", task_id, snapshot_id)
    except Exception as exc:
        logger.exception("快照创建任务 %s 失败", task_id)
        if dest_path.is_file():
            dest_path.unlink(missing_ok=True)
        await _mark_task_failure(task_id, str(exc))


async def async_snapshot_restore(
    task_id: str,
    src: str,
    dest: str,
    snapshot_id: str,
) -> None:
    src_path = Path(src)
    dest_path = Path(dest)
    try:
        await snapshot_image_to_file(task_id, src_path, dest_path)
        async with SessionLocal() as session:
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "SUCCESS"
            task.progress = 100
            task.result_ref = snapshot_id
            await session.commit()
        logger.info("快照恢复任务 %s 完成 snapshot=%s", task_id, snapshot_id)
    except Exception as exc:
        logger.exception("快照恢复任务 %s 失败", task_id)
        await _mark_task_failure(task_id, str(exc))


@celery_app.task(name="app.tasks.snapshot_ops.run_snapshot_create")
def run_snapshot_create(
    task_id: str,
    instance_id: str,
    src: str,
    dest: str,
    name: str,
    snapshot_id: str,
) -> None:
    logger.info("Celery 接收到快照创建任务: %s", task_id)
    asyncio.run(async_snapshot_create(task_id, instance_id, src, dest, name, snapshot_id))


@celery_app.task(name="app.tasks.snapshot_ops.run_snapshot_restore")
def run_snapshot_restore(
    task_id: str,
    instance_id: str,
    src: str,
    dest: str,
    snapshot_id: str,
) -> None:
    logger.info("Celery 接收到快照恢复任务: %s snapshot=%s", task_id, snapshot_id)
    asyncio.run(async_snapshot_restore(task_id, src, dest, snapshot_id))
