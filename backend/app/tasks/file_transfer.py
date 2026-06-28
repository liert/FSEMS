# -*- coding: utf-8 -*-
import asyncio
import logging
import posixpath
import hashlib
import asyncssh
import redis.asyncio as aioredis
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
    key = f"fsems:fs_cache:{instance_id}:{path_hash}"
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.delete(key)
        await r.close()
        logger.info(f"成功清理缓存键: {key}")
    except Exception as e:
        logger.warning(f"清理 Redis 缓存失败: {e}")

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
        
        # 任务启动，设置状态为 RUNNING，进度 50%
        task.status = "RUNNING"
        task.progress = 50
        await session.commit()

        try:
            # 获取实例及其关联模板信息
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

            # 建立 SSH 联通会话
            async with await get_ssh_connection(host, port) as conn:
                if direction == "host_to_guest":
                    logger.info(f"SCP 传输中: 宿主机 {src} -> 访客机 {dest}")
                    # 使用 legacy SCP 协议 (use_sftp=False) 以兼容 OpenWrt 上的 Dropbear，添加 recurse=True 支持文件夹传输
                    await asyncssh.scp(src, (conn, dest), recurse=True, use_sftp=False)
                    # 写入成功后清空访客机缓存
                    await invalidate_cache(instance.id, dest)
                elif direction == "guest_to_host":
                    logger.info(f"SCP 传输中: 访客机 {src} -> 宿主机 {dest}")
                    await asyncssh.scp((conn, src), dest, recurse=True, use_sftp=False)
                else:
                    raise ValueError(f"不支持的传输方向: {direction}")

            # 传输成功，更新任务状态
            # 重新获取对象以防 session 状态冲突
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
