# -*- coding: utf-8 -*-
import asyncio
import contextlib
import logging
import posixpath
import hashlib
import asyncssh
import redis.asyncio as aioredis
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import get_settings
from app.models.task import Task
from app.models.instance import Instance
from app.services.ssh_service import get_ssh_connection

logger = logging.getLogger(__name__)


async def invalidate_cache(instance_id: str, dest_path: str):
    """
    在成功传输文件到访客机后，主动清除目标父目录的 Redis 缓存。
    """
    settings = get_settings()
    parent = posixpath.dirname(dest_path)
    path_hash = hashlib.sha256(parent.encode()).hexdigest()
    key = f"fsems:fs_cache:online:{instance_id}:{path_hash}"
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.delete(key)
        await r.close()
        logger.info(f"成功清理缓存键: {key}")
    except Exception as e:
        logger.warning(f"清理 Redis 缓存失败: {e}")


async def _set_task_progress(task_id: str, progress: int, status: str | None = None) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        task.progress = progress
        if status:
            task.status = status
        await session.commit()


def _estimate_transfer_total(direction: str, src: str, dest: str) -> int | None:
    """Best-effort total bytes for single-file transfers."""
    if direction == "host_to_guest":
        path = Path(src)
    else:
        path = Path(dest)
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return None
    return None


def _progress_from_bytes(bytes_transferred: int, total_bytes: int | None) -> int:
    if total_bytes and total_bytes > 0:
        return min(99, int(bytes_transferred * 100 / total_bytes))
    if bytes_transferred <= 0:
        return 5
    # Unknown total (directory): scale slowly by volume transferred
    return min(92, 5 + int(bytes_transferred / (512 * 1024)))


async def async_file_transfer(task_id: str, direction: str, src: str, dest: str):
    """
    异步执行文件传输，并更新任务数据库状态。
    """
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error(f"未能在数据库中找到任务 ID: {task_id}")
            return

        task.status = "RUNNING"
        task.progress = 5
        await session.commit()

        try:
            result = await session.execute(
                select(Instance)
                .options(selectinload(Instance.template))
                .where(Instance.id == task.instance_id)
            )
            instance = result.scalar_one_or_none()
            if not instance:
                raise ValueError("未找到对应的 QEMU 实例")

            template = instance.template
            host = instance.guest_ssh_host or template.guest_ssh_host
            port = template.guest_ssh_port

            estimated_total = _estimate_transfer_total(direction, src, dest)
            progress_state = {"bytes": 0, "total": estimated_total, "last_pct": 5, "done": False}

            async def progress_poller():
                while not progress_state["done"]:
                    pct = _progress_from_bytes(progress_state["bytes"], progress_state["total"])
                    if pct >= progress_state["last_pct"] + 3:
                        progress_state["last_pct"] = pct
                        await _set_task_progress(task_id, pct)
                    await asyncio.sleep(0.4)

            def progress_handler(_srcpath, _dstpath, bytes_transferred, total_bytes):
                progress_state["bytes"] = bytes_transferred
                if total_bytes:
                    progress_state["total"] = total_bytes

            poller_task = asyncio.create_task(progress_poller())
            try:
                async with await get_ssh_connection(host, port) as conn:
                    if direction == "host_to_guest":
                        logger.info(f"SCP 传输中: 宿主机 {src} -> 访客机 {dest}")
                        await asyncssh.scp(
                            src,
                            (conn, dest),
                            recurse=True,
                            use_sftp=False,
                            progress_handler=progress_handler,
                        )
                        await invalidate_cache(instance.id, dest)
                    elif direction == "guest_to_host":
                        logger.info(f"SCP 传输中: 访客机 {src} -> 宿主机 {dest}")
                        await asyncssh.scp(
                            (conn, src),
                            dest,
                            recurse=True,
                            use_sftp=False,
                            progress_handler=progress_handler,
                        )
                    else:
                        raise ValueError(f"不支持的传输方向: {direction}")
            finally:
                progress_state["done"] = True
                poller_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await poller_task

            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "SUCCESS"
            task.progress = 100
            await session.commit()
            logger.info(f"文件传输任务 {task_id} 成功完成")

        except Exception as e:
            logger.exception(f"文件传输任务 {task_id} 执行出错")
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "FAILURE"
            task.progress = 100
            task.error_msg = str(e)
            await session.commit()


@celery_app.task(name="app.tasks.file_transfer.run_file_transfer")
def run_file_transfer(task_id: str, direction: str, src: str, dest: str):
    """
    Celery 异步任务入口，使用 asyncio.run 运行异步文件传输协程。
    """
    logger.info(f"Celery 接收到传输任务: {task_id}, 方向: {direction}")
    asyncio.run(async_file_transfer(task_id, direction, src, dest))
