# -*- coding: utf-8 -*-
"""双栏文件传输：默认走 iot-tools（legacy scp + ELF 依赖），失败可回退 asyncssh。"""

import asyncio
import contextlib
import hashlib
import logging
import posixpath
from pathlib import Path

import asyncssh
import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.instance import Instance
from app.models.task import Task
from app.services import iot_tools_client
from app.services.ssh_service import get_ssh_connection

logger = logging.getLogger(__name__)


async def invalidate_cache(instance_id: str, dest_path: str):
    """传输到访客机后清除在线目录缓存。"""
    settings = get_settings()
    parent = posixpath.dirname(dest_path)
    path_hash = hashlib.sha256(parent.encode()).hexdigest()
    key = f"fsems:fs_cache:online:{instance_id}:{path_hash}"
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.delete(key)
        await r.close()
        logger.info("成功清理缓存键: %s", key)
    except Exception as e:
        logger.warning("清理 Redis 缓存失败: %s", e)


async def _set_task_progress(task_id: str, progress: int, status: str | None = None) -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one()
        task.progress = min(100, max(0, int(progress)))
        if status:
            task.status = status
        await session.commit()


def _estimate_transfer_total(direction: str, src: str, dest: str) -> int | None:
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
    return min(92, 5 + int(bytes_transferred / (512 * 1024)))


async def _transfer_via_iot_tools(
    direction: str,
    src: str,
    dest: str,
    *,
    host: str,
    port: int,
    task_id: str,
) -> None:
    """使用 iot-tools 完成传输。"""

    async def bump(pct: int) -> None:
        await _set_task_progress(task_id, pct)

    await bump(10)

    if direction == "host_to_guest":
        # dest 可能是完整远端文件路径
        search_root = Path(src).parent
        logger.info("iot-tools push: %s -> %s:%s (search_root=%s)", src, host, dest, search_root)
        await iot_tools_client.scp_host_to_guest(
            src,
            host,
            dest,
            port=port,
            search_root=search_root,
            progress=bump,
        )
    elif direction == "guest_to_host":
        logger.info("iot-tools pull: %s:%s -> %s", host, src, dest)
        await iot_tools_client.scp_guest_to_host(
            host,
            src,
            dest,
            port=port,
            progress=bump,
        )
    else:
        raise ValueError(f"不支持的传输方向: {direction}")


async def _transfer_via_asyncssh(
    direction: str,
    src: str,
    dest: str,
    *,
    host: str,
    port: int,
    task_id: str,
) -> None:
    """asyncssh 回退路径（iot-tools 不可用或失败时）。"""
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
                logger.info("asyncssh SCP: 宿主机 %s -> 访客机 %s", src, dest)
                await asyncssh.scp(
                    src,
                    (conn, dest),
                    recurse=True,
                    use_sftp=False,
                    progress_handler=progress_handler,
                )
            elif direction == "guest_to_host":
                logger.info("asyncssh SCP: 访客机 %s -> 宿主机 %s", src, dest)
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


async def async_file_transfer(task_id: str, direction: str, src: str, dest: str):
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            logger.error("未能在数据库中找到任务 ID: %s", task_id)
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
            port = int(template.guest_ssh_port or 22)

            use_iot = iot_tools_client.iot_tools_available()
            if use_iot:
                try:
                    await _transfer_via_iot_tools(
                        direction, src, dest, host=host, port=port, task_id=task_id
                    )
                except Exception as iot_err:
                    logger.warning(
                        "iot-tools 传输失败，回退 asyncssh: %s",
                        iot_err,
                        exc_info=True,
                    )
                    await _set_task_progress(task_id, 15)
                    await _transfer_via_asyncssh(
                        direction, src, dest, host=host, port=port, task_id=task_id
                    )
            else:
                logger.warning("iot-tools 不可用，使用 asyncssh SCP")
                await _transfer_via_asyncssh(
                    direction, src, dest, host=host, port=port, task_id=task_id
                )

            if direction == "host_to_guest":
                await invalidate_cache(instance.id, dest)

            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "SUCCESS"
            task.progress = 100
            await session.commit()
            logger.info("文件传输任务 %s 成功完成", task_id)

        except Exception as e:
            logger.exception("文件传输任务 %s 执行出错", task_id)
            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "FAILURE"
            task.progress = 100
            task.error_msg = str(e)
            await session.commit()


@celery_app.task(name="app.tasks.file_transfer.run_file_transfer")
def run_file_transfer(task_id: str, direction: str, src: str, dest: str):
    logger.info("Celery 接收到传输任务: %s, 方向: %s", task_id, direction)
    asyncio.run(async_file_transfer(task_id, direction, src, dest))
