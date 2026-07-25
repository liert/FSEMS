from contextlib import asynccontextmanager
from contextlib import AsyncExitStack

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

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


class McpTokenMiddleware(BaseHTTPMiddleware):
    """可选：MCP 路径要求 Bearer token（MCP_TOKEN 非空时启用）。"""

    def __init__(self, app, path_prefix: str, token: str):
        super().__init__(app)
        self.path_prefix = path_prefix.rstrip("/") or "/mcp"
        self.token = token

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == self.path_prefix or path.startswith(self.path_prefix + "/"):
            auth = request.headers.get("authorization") or ""
            expected = f"Bearer {self.token}"
            if auth != expected:
                return Response(
                    content='{"jsonrpc":"2.0","error":{"code":-32001,"message":"Unauthorized"},"id":null}',
                    status_code=401,
                    media_type="application/json",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)


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

    # 3. MCP Streamable HTTP session manager
    async with AsyncExitStack() as stack:
        if settings.MCP_ENABLED and getattr(_app.state, "mcp_session_manager", None) is not None:
            logger.info("启动 MCP Streamable HTTP session manager (path=%s)", settings.MCP_PATH)
            await stack.enter_async_context(_app.state.mcp_session_manager.run())
        yield

    # 4. 优雅关闭 Celery 工作进程
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

    # --- MCP Streamable HTTP ---
    if settings.MCP_ENABLED:
        from app.mcp_server import get_mcp, mcp_asgi_app

        get_mcp()  # 注册 tools/resources
        mcp_app = mcp_asgi_app()
        # session manager 由 streamable_http_app() 懒创建
        app.state.mcp_session_manager = get_mcp().session_manager
        mount_path = settings.MCP_PATH.rstrip("/") or "/mcp"
        from mcp.server.fastmcp.server import StreamableHTTPASGIApp
        from starlette.routing import Route

        _streamable = StreamableHTTPASGIApp(get_mcp().session_manager)

        class _McpEndpoint:
            """
            将 /mcp 与 /mcp/ 均映射到 Streamable HTTP，避免 Mount 的 307 重定向
            （部分 MCP 客户端不会自动跟随 POST 重定向）。
            """

            def __init__(self, inner, prefix: str):
                self.inner = inner
                self.prefix = prefix

            async def __call__(self, scope, receive, send):
                if scope["type"] in ("http", "websocket"):
                    scope = dict(scope)
                    scope["path"] = "/"
                    scope["raw_path"] = b"/"
                    scope["root_path"] = (scope.get("root_path") or "") + self.prefix
                await self.inner(scope, receive, send)

        endpoint = _McpEndpoint(_streamable, mount_path)
        # 插到最前，优先于其它路由
        app.router.routes.insert(0, Route(mount_path, endpoint=endpoint, methods=["GET", "POST", "DELETE"]))
        app.router.routes.insert(0, Route(mount_path + "/", endpoint=endpoint, methods=["GET", "POST", "DELETE"]))
        if settings.MCP_TOKEN:
            app.add_middleware(McpTokenMiddleware, path_prefix=mount_path, token=settings.MCP_TOKEN)
        logger.info("MCP Streamable HTTP endpoints: %s and %s/", mount_path, mount_path)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_model=ApiResponse[dict])
    async def root() -> ApiResponse[dict]:
        data = {"service": "FSEMS"}
        if settings.MCP_ENABLED:
            data["mcp"] = {
                "transport": "streamable-http",
                "path": settings.MCP_PATH,
                "auth": bool(settings.MCP_TOKEN),
            }
        return ApiResponse(data=data, message="OK")

    return app


app = create_app()
