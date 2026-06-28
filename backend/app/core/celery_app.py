# -*- coding: utf-8 -*-
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

# 初始化 Celery 实例，使用 Redis 作为消息中间件 (Broker) 与结果后端 (Backend)
celery_app = Celery(
    "fsems",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.file_transfer"]
)

# Celery 参数配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
