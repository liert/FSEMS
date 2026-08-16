# -*- coding: utf-8 -*-
"""
双栏文件传输：仅通过 iot-tools（系统 scp/ssh，可选 sshpass）。

iot-tools 本身不依赖 asyncssh；asyncssh 仅用于 FSEMS 其它能力
（在线 guest 目录列表等），不参与本任务。
"""

import hashlib
import logging
import posixpath
from pathlib import Path

import redis.asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.instance import Instance
from app.models.task import Task
from app.services import iot_tools_client
from app.services.host_fs import resolve_instance_host_root

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


def _progress_from_bytes(bytes_transferred: int, total_bytes: int | None) -> int:
    """保留供单元测试 / 后续进度增强使用。"""
    if total_bytes and total_bytes > 0:
        return min(99, int(bytes_transferred * 100 / total_bytes))
    if bytes_transferred <= 0:
        return 5
    return min(92, 5 + int(bytes_transferred / (512 * 1024)))


def _dependency_search_root(instance_id: str, source_path: str) -> Path:
    """Host→guest 推送 ELF 时的 iot-tools 依赖搜索根。

    iot-tools 会从 search_root 向下查找 NEEDED 库，并按相对路径映射到 guest
    （rootfs/usr/lib/... → /usr/lib/...）。双栏文件管理器中宿主机面板的根就是
    实例自定义 RootFS 解压目录，因此源文件位于实例根内时必须以实例根作为
    search_root；若仍用文件所在目录，依赖只会扫描 usr/bin 等单层目录，最终
    出现“只传了 dbus-daemon、没有传 libdbus/libexpat 等依赖”的问题。
    """
    # 注意：这里不能 resolve()。传输软链接时 source_path 是链接条目本身，
    # resolve 后会退化成真实目标文件，导致搜索根选错（绝对链接尤其明显）。
    source = Path(source_path).absolute()
    instance_root = resolve_instance_host_root(instance_id)
    try:
        source.relative_to(instance_root)
    except ValueError:
        return source.parent
    return instance_root


async def _transfer_via_iot_tools(
    direction: str,
    src: str,
    dest: str,
    *,
    host: str,
    port: int,
    task_id: str,
    search_root: Path | None = None,
) -> None:
    async def bump(pct: int) -> None:
        await _set_task_progress(task_id, pct)

    await bump(10)

    if direction == "host_to_guest":
        search_root = search_root or Path(src).parent
        logger.info(
            "[task=%s] iot-tools push: %s -> %s:%s (search_root=%s)",
            task_id,
            src,
            host,
            dest,
            search_root,
        )

        def record_iot_line(line: str) -> None:
            # iot-tools 的每一行都对应一个实际复制项（主文件或 ELF 依赖）。
            logger.info("[task=%s] iot-tools | %s", task_id, line)

        await iot_tools_client.scp_host_to_guest(
            src,
            host,
            dest,
            port=port,
            search_root=search_root,
            progress=bump,
            on_line=record_iot_line,
        )
        logger.info("[task=%s] iot-tools push 完成", task_id)
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
            if not iot_tools_client.iot_tools_available():
                raise RuntimeError(
                    "iot-tools 不可用（当前解释器无法 import iot_tools）。"
                    f"请用同一虚拟环境安装: {__import__('sys').executable} -m pip install -e "
                    f"{__import__('pathlib').Path(__file__).resolve().parents[3] / 'third_party' / 'iot-tools'}"
                )

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

            search_root = None
            if direction == "host_to_guest":
                search_root = _dependency_search_root(instance.id, src)

            await _transfer_via_iot_tools(
                direction,
                src,
                dest,
                host=host,
                port=port,
                task_id=task_id,
                search_root=search_root,
            )

            if direction == "host_to_guest":
                await invalidate_cache(instance.id, dest)

            result = await session.execute(select(Task).where(Task.id == task_id))
            task = result.scalar_one()
            task.status = "SUCCESS"
            task.progress = 100
            await session.commit()
            logger.info("文件传输任务 %s 成功完成 (iot-tools)", task_id)

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
    import asyncio

    logger.info("Celery 接收到传输任务: %s, 方向: %s (iot-tools only)", task_id, direction)
    asyncio.run(async_file_transfer(task_id, direction, src, dest))
