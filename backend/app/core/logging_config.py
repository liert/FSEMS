import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(logs_dir: str) -> None:
    log_file = Path(logs_dir) / "fastapi.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # 根日志记录器设置
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 检查是否已配置 RotatingFileHandler，避免重复添加
    has_file_handler = any(
        isinstance(h, RotatingFileHandler) and Path(h.baseFilename).resolve() == log_file.resolve()
        for h in root_logger.handlers
    )
    
    if not has_file_handler:
        # 使用 10MB 的轮转日志，保留最近 5 个日志文件
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        # 日志等级英文大写，中文日志格式
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        
        # 确保 uvicorn 相关的 logger 也输出到同一个日志文件
        for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
            uv_logger = logging.getLogger(logger_name)
            # 避免重复添加
            if not any(isinstance(h, RotatingFileHandler) for h in uv_logger.handlers):
                uv_logger.addHandler(file_handler)
                
        # 打印初始化完成日志（中文日志，日志等级英文大写）
        root_logger.info("系统日志服务初始化成功，日志输出路径: %s", log_file.as_posix())


def setup_celery_logging(logs_dir: str) -> None:
    """为 Celery worker 挂载 celery.log，记录 iot-tools 逐文件传输明细。

    Celery 默认把日志写到 stderr，而 FSEMS 自动拉起 worker 时 stderr 指向
    DEVNULL，导致「系统日志 → Celery」页一直是空的。这里给根 logger 增加一个
    独立的 RotatingFileHandler，app.services.iot_tools_client 与
    app.tasks.file_transfer 的 INFO 日志都会随之落到 celery.log。
    """
    log_file = Path(logs_dir) / "celery.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    resolved = log_file.resolve()
    has_file_handler = any(
        isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename).resolve() == resolved
        for handler in root_logger.handlers
    )
    if has_file_handler:
        return

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.info("Celery 日志文件已初始化: %s", log_file.as_posix())
