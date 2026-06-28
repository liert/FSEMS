from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.schemas.common import ApiResponse


import subprocess
import logging
from pathlib import Path
import redis

logger = logging.getLogger(__name__)

def ensure_redis_service(settings) -> bool:
    import os
    redis_client = redis.from_url(settings.REDIS_URL)
    try:
        redis_client.ping()
        return True
    except Exception:
        pass
    
    logger.warning("检测到 Redis 服务未运行，正在尝试自动拉起...")
    is_root = os.getuid() == 0 if hasattr(os, "getuid") else False
    
    try:
        # 如果当前进程是 root，可直接运行 systemctl。如果不是，尝试非交互式 sudo -n 启动。
        cmd = ["systemctl", "start", "redis-server"]
        if not is_root:
            cmd = ["sudo", "-n", "systemctl", "start", "redis-server"]
            
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        if proc.returncode == 0:
            import time
            time.sleep(1)
            try:
                redis_client.ping()
                logger.info("Redis 服务自动拉起并连接成功！")
                return True
            except Exception:
                pass
        
        err_msg = stderr.decode().strip()
        logger.error(
            f"【环境警告】Redis 服务未启动且自动拉起失败（当前运行用户非 root 或无免密 sudo 权限）。\n"
            f"👉 请以 sudo 启动后端服务以授权自动拉起: sudo ../backend/.venv/bin/uvicorn app.main:app --reload\n"
            f"👉 或者在终端手动运行命令启动服务: sudo systemctl start redis-server"
        )
    except Exception as e:
        logger.error(
            f"【环境警告】尝试启动 Redis 服务时发生异常: {e}\n"
            f"👉 请在终端手动执行命令启动服务: sudo systemctl start redis-server"
        )
    return False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    await init_db()

    # 1. 自动校验并启动 Redis 依赖服务
    redis_ready = ensure_redis_service(settings)

    # 2. 自动在子进程中拉起 Celery 异步队列
    celery_proc = None
    if redis_ready:
        try:
            import sys
            celery_bin = str(Path(sys.executable).parent / "celery")
            cmd = [celery_bin, "-A", "app.core.celery_app", "worker", "--loglevel=warning"]
            if not Path("app/core/celery_app.py").exists() and Path("backend/app/core/celery_app.py").exists():
                cmd += ["--workdir", "backend"]
            
            logger.info("正在自动启动后台 Celery 任务队列服务...")
            celery_proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _app.state.celery_proc = celery_proc
            logger.info("Celery 队列服务已在后台启动完成。")
        except Exception as e:
            logger.warning(
                f"自动拉起 Celery 服务失败: {e}。\n"
                f"👉 如果需要异步文件传输，请手动执行: celery -A app.core.celery_app worker --loglevel=info"
            )
    else:
        logger.warning("由于 Redis 离线，已跳过自动运行 Celery 服务。")

    yield

    # 3. 优雅关闭 Celery 工作进程
    celery_proc = getattr(_app.state, "celery_proc", None)
    if celery_proc:
        logger.info("正在关闭后台 Celery 队列服务...")
        try:
            celery_proc.terminate()
            celery_proc.wait(timeout=5)
            logger.info("Celery 队列服务已优雅退出。")
        except Exception:
            try:
                celery_proc.kill()
            except Exception:
                pass


def create_app() -> FastAPI:
    settings = get_settings()
    settings.ensure_dirs()
    
    # 初始化日志配置
    from app.core.logging_config import setup_logging
    setup_logging(settings.LOGS_DIR)

    app = FastAPI(title="FSEMS", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_model=ApiResponse[dict])
    async def root() -> ApiResponse[dict]:
        return ApiResponse(data={"service": "FSEMS"}, message="OK")

    return app


app = create_app()
# Trigger reload: Redis started
