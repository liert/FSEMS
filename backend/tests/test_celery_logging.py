import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.logging_config import setup_celery_logging


def test_setup_celery_logging_attaches_handler_idempotently(tmp_path):
    root = logging.getLogger()
    log_file = (tmp_path / "celery.log").resolve()

    setup_celery_logging(str(tmp_path))
    handlers = [
        handler
        for handler in root.handlers
        if isinstance(handler, RotatingFileHandler)
        and Path(handler.baseFilename).resolve() == log_file
    ]

    try:
        assert len(handlers) == 1
        assert handlers[0].level == logging.INFO

        # 重复调用不应重复挂载 handler
        setup_celery_logging(str(tmp_path))
        handlers_after = [
            handler
            for handler in root.handlers
            if isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == log_file
        ]
        assert len(handlers_after) == 1
    finally:
        for handler in handlers:
            root.removeHandler(handler)
            handler.close()
