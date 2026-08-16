# -*- coding: utf-8 -*-
from celery import Celery, signals
from app.core.config import get_settings
from app.core.logging_config import setup_celery_logging

settings = get_settings()

# 初始化 Celery 实例，使用 Redis 作为消息中间件 (Broker) 与结果后端 (Backend)
celery_app = Celery(
    "fsems",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.file_transfer", "app.tasks.snapshot_ops"]
)

# Celery 参数配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


def _attach_celery_log_file(**_kwargs: object) -> None:
    """Celery 完成自身日志初始化后，把根 logger 输出追加到 celery.log。

    使用 after_setup_logger / after_setup_task_logger 而不是 setup_logging：
    连接 setup_logging 会禁止 Celery 执行默认日志初始化，影响控制台输出。
    """
    setup_celery_logging(get_settings().LOGS_DIR)


signals.after_setup_logger.connect(_attach_celery_log_file)
signals.after_setup_task_logger.connect(_attach_celery_log_file)
