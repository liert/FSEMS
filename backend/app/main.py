from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.schemas.common import ApiResponse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


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
