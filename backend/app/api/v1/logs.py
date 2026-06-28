import json
import logging
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.schemas.common import ApiResponse
from app.schemas.logs import (
    BackendLogsOut,
    FrontendLogCreate,
    FrontendLogOut,
    FrontendLogsOut,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["logs"])
settings = get_settings()


@router.get("/backend", response_model=ApiResponse[BackendLogsOut])
async def get_backend_logs(
    type: str = Query("fastapi"),
    lines: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _user: str = Depends(get_current_user),
) -> ApiResponse[BackendLogsOut]:
    if type not in ("fastapi", "celery"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "LOG_FILE_READ_FAILED",
                "message": "不支持的日志类型，只能是 fastapi 或 celery",
            },
        )

    filename = "fastapi.log" if type == "fastapi" else "celery.log"
    log_file = Path(settings.LOGS_DIR) / filename

    if not log_file.exists():
        return ApiResponse(
            data=BackendLogsOut(log_type=type, total_lines=0, lines=[]),
            message="日志文件为空或不存在",
        )

    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        
        # 清除换行符并逆序（最新日志在最前）
        all_lines = [l.rstrip("\r\n") for l in all_lines]
        all_lines.reverse()

        total = len(all_lines)
        sliced = all_lines[offset : offset + lines]

        return ApiResponse(
            data=BackendLogsOut(log_type=type, total_lines=total, lines=sliced),
            message="获取后端日志成功",
        )
    except Exception as e:
        logger.error("读取后端日志文件失败: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "LOG_FILE_READ_FAILED",
                "message": f"读取日志文件失败: {str(e)}",
            },
        )


@router.post("/frontend", response_model=ApiResponse[None])
async def report_frontend_log(
    body: FrontendLogCreate,
) -> ApiResponse[None]:
    try:
        log_file = Path(settings.LOGS_DIR) / "frontend_client.log"
        # 确保日志文件夹存在
        log_file.parent.mkdir(parents=True, exist_ok=True)

        log_entry = {
            "level": body.level.upper(),
            "message": body.message,
            "stack": body.stack,
            "url": body.url,
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        return ApiResponse(data=None, message="客户端日志上报成功")
    except Exception as e:
        logger.error("写入前端客户端日志失败: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "LOG_FILE_READ_FAILED",
                "message": f"上报日志失败: {str(e)}",
            },
        )


@router.get("/frontend", response_model=ApiResponse[FrontendLogsOut])
async def get_frontend_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _user: str = Depends(get_current_user),
) -> ApiResponse[FrontendLogsOut]:
    log_file = Path(settings.LOGS_DIR) / "frontend_client.log"

    if not log_file.exists():
        return ApiResponse(
            data=FrontendLogsOut(logs=[]),
            message="前端日志为空",
        )

    try:
        logs = []
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    logs.append(data)
                except Exception:
                    continue

        # 赋予虚拟自增 ID，并逆序排列（最新在最前）
        for idx, item in enumerate(logs):
            item["id"] = idx + 1
        
        logs.reverse()

        sliced = logs[offset : offset + limit]
        out_logs = [FrontendLogOut(**item) for item in sliced]

        return ApiResponse(
            data=FrontendLogsOut(logs=out_logs),
            message="获取前端日志成功",
        )
    except Exception as e:
        logger.error("读取前端日志文件失败: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "LOG_FILE_READ_FAILED",
                "message": f"读取日志文件失败: {str(e)}",
            },
        )
