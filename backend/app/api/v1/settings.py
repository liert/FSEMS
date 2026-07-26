# -*- coding: utf-8 -*-
"""系统设置读写接口（密码仅可写入，读取只返回是否已设置）。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.core.config import get_settings, reload_settings
from app.core import settings_store
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/settings", tags=["settings"])


class SystemSettingsOut(BaseModel):
    """可安全展示给前端的系统配置（含可编辑字段当前值）。"""

    # 路径
    workspace: str
    kernels_dir: str
    rootfs_dir: str
    mnt_dir: str
    logs_dir: str
    database_path: str | None = None

    # 网络 / QEMU
    bridge: str
    boot_timeout_sec: int
    qemu_serial_dir: str
    fsems_user: str

    # 访客 SSH
    guest_ssh_user: str
    guest_ssh_password_set: bool = False

    # OpenWrt
    openwrt_download_base: str

    # MCP（随 API 进程启动）
    mcp_enabled: bool
    mcp_path: str
    mcp_stateless: bool
    mcp_auth_required: bool

    # 认证
    admin_user: str
    jwt_expire_seconds: int

    # API
    api_host: str
    api_port: int
    redis_url_masked: str

    # 元信息
    override_file: str = ""
    restart_hint: str = "部分项（如 MCP 启停、挂载路径）需重启后端进程后完全生效"


class SystemSettingsUpdate(BaseModel):
    """可更新字段；密码/token/redis 留空表示不修改。"""

    workspace: str | None = Field(None, max_length=512)
    kernels_dir: str | None = Field(None, max_length=512)
    rootfs_dir: str | None = Field(None, max_length=512)
    mnt_dir: str | None = Field(None, max_length=512)
    logs_dir: str | None = Field(None, max_length=512)

    bridge: str | None = Field(None, max_length=64)
    boot_timeout_sec: int | None = Field(None, ge=10, le=3600)
    qemu_serial_dir: str | None = Field(None, max_length=512)
    fsems_user: str | None = Field(None, max_length=64)

    guest_ssh_user: str | None = Field(None, max_length=64)
    guest_ssh_password: str | None = Field(None, max_length=256)

    openwrt_download_base: str | None = Field(None, max_length=512)

    mcp_enabled: bool | None = None
    mcp_path: str | None = Field(None, max_length=64)
    mcp_stateless: bool | None = None
    mcp_token: str | None = Field(None, max_length=256)

    admin_user: str | None = Field(None, min_length=1, max_length=64)
    admin_password: str | None = Field(None, max_length=256)
    jwt_expire_seconds: int | None = Field(None, ge=60, le=2592000)

    api_host: str | None = Field(None, max_length=128)
    api_port: int | None = Field(None, ge=1, le=65535)
    redis_url: str | None = Field(None, max_length=512)


def _mask_redis(url: str) -> str:
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, hostpart = rest.rsplit("@", 1)
            if ":" in creds:
                user, _pw = creds.split(":", 1)
                return f"{scheme}://{user + ':' if user else ''}***@{hostpart}"
            return f"{scheme}://***@{hostpart}"
    return url


def _to_out() -> SystemSettingsOut:
    s = get_settings()
    db_path = s.database_path
    return SystemSettingsOut(
        workspace=str(s.workspace_path),
        kernels_dir=str(s.kernels_path),
        rootfs_dir=str(s.rootfs_path),
        mnt_dir=str(s.FSEMS_MNT_DIR),
        logs_dir=str(s.LOGS_DIR),
        database_path=str(db_path) if db_path else None,
        bridge=s.FSEMS_BRIDGE,
        boot_timeout_sec=s.BOOT_TIMEOUT_SEC,
        qemu_serial_dir=s.QEMU_SERIAL_DIR,
        fsems_user=s.fsems_user,
        guest_ssh_user=s.FSEMS_GUEST_SSH_USER,
        guest_ssh_password_set=bool(s.FSEMS_GUEST_SSH_PASSWORD),
        openwrt_download_base=s.OPENWRT_DOWNLOAD_BASE,
        mcp_enabled=s.MCP_ENABLED,
        mcp_path=s.MCP_PATH,
        mcp_stateless=s.MCP_STATELESS,
        mcp_auth_required=bool(s.MCP_TOKEN),
        admin_user=s.FSEMS_ADMIN_USER,
        jwt_expire_seconds=s.JWT_EXPIRE_SECONDS,
        api_host=s.API_HOST,
        api_port=s.API_PORT,
        redis_url_masked=_mask_redis(s.REDIS_URL),
        override_file=str(settings_store.override_path()),
    )


@router.get("/system", response_model=ApiResponse[SystemSettingsOut])
async def get_system_settings(
    _user: str = Depends(get_current_user),
) -> ApiResponse[SystemSettingsOut]:
    return ApiResponse(data=_to_out(), message="System settings fetched")


@router.put("/system", response_model=ApiResponse[SystemSettingsOut])
async def update_system_settings(
    body: SystemSettingsUpdate,
    _user: str = Depends(get_current_user),
) -> ApiResponse[SystemSettingsOut]:
    """更新可编辑设置，持久化到 data/settings.override.json 并热加载。"""
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "EMPTY_PATCH", "message": "未提供任何可修改字段"},
        )
    try:
        settings_store.apply_patch(patch)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "INVALID_SETTINGS", "message": str(exc)},
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SAVE_FAILED", "message": f"保存失败: {exc}"},
        ) from exc

    reload_settings()
    # 确保目录存在
    try:
        get_settings().ensure_dirs()
    except Exception:
        pass

    return ApiResponse(
        data=_to_out(),
        message="设置已保存。MCP 启停或挂载路径变更需重启后端后完全生效",
    )
