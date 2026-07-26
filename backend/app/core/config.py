from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_REPO_ROOT / ".env", _REPO_ROOT / ".env.example"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = ""
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    FSEMS_WORKSPACE: str = ""
    FSEMS_MNT_DIR: str = ""
    FSEMS_KERNELS_DIR: str = ""
    FSEMS_ROOTFS_DIR: str = ""
    LOGS_DIR: str = ""
    OPENWRT_DOWNLOAD_BASE: str = "https://downloads.openwrt.org"

    # MCP Streamable HTTP（随 API 进程启动并挂载）
    MCP_ENABLED: bool = True
    MCP_PATH: str = "/mcp"
    MCP_STATELESS: bool = True
    MCP_JSON_RESPONSE: bool = False
    MCP_TOKEN: str = ""  # 非空时要求 Authorization: Bearer <token>

    FSEMS_BRIDGE: str = "br_fsems"
    QEMU_SERIAL_DIR: str = "/tmp"
    BOOT_TIMEOUT_SEC: int = 120
    FSEMS_USER: str = ""

    FSEMS_GUEST_SSH_USER: str = "root"
    FSEMS_GUEST_SSH_PASSWORD: str = ""

    # iot-tools 子模块 CLI（默认 PATH 中的 iot-tools；可填绝对路径）
    IOT_TOOLS_BIN: str = "iot-tools"

    FSEMS_ADMIN_USER: str = "admin"
    FSEMS_ADMIN_PASSWORD: str = "admin"
    SECRET_KEY: str = "change-me-in-production"
    JWT_EXPIRE_SECONDS: int = 3600

    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def default_database_url(cls, v: str) -> str:
        if v:
            if v.startswith("sqlite+aiosqlite:///./"):
                rel = v.removeprefix("sqlite+aiosqlite:///")
                abs_path = (_REPO_ROOT / rel).resolve().as_posix()
                return f"sqlite+aiosqlite:///{abs_path}"
            return v
        db_file = (_REPO_ROOT / "data" / "fsems.db").resolve().as_posix()
        return f"sqlite+aiosqlite:///{db_file}"

    @field_validator("FSEMS_WORKSPACE", mode="before")
    @classmethod
    def default_workspace(cls, v: str) -> str:
        if v:
            if v.startswith("./"):
                return str((_REPO_ROOT / v.removeprefix("./")).resolve())
            return v
        return str((_REPO_ROOT / "data" / "workspace").resolve())

    @field_validator("FSEMS_MNT_DIR", mode="before")
    @classmethod
    def default_mnt_dir(cls, v: str) -> str:
        if v:
            if v.startswith("./"):
                return str((_REPO_ROOT / v.removeprefix("./")).resolve())
            return v
        return str((_REPO_ROOT / "data" / "mnt").resolve())

    @field_validator("LOGS_DIR", mode="before")
    @classmethod
    def default_logs_dir(cls, v: str) -> str:
        if v:
            if v.startswith("./"):
                return str((_REPO_ROOT / v.removeprefix("./")).resolve())
            return v
        import os
        db_url = os.environ.get("DATABASE_URL", "")
        if db_url and not db_url.startswith("sqlite+aiosqlite:///./") and "data/fsems.db" not in db_url:
            return "/var/fsems/logs"
        return str((_REPO_ROOT / "data" / "logs").resolve())

    @field_validator("FSEMS_KERNELS_DIR", mode="before")
    @classmethod
    def default_kernels_dir(cls, v: str) -> str:
        if v:
            if v.startswith("./"):
                return str((_REPO_ROOT / v.removeprefix("./")).resolve())
            return v
        return str((_REPO_ROOT / "data" / "kernels").resolve())

    @field_validator("FSEMS_ROOTFS_DIR", mode="before")
    @classmethod
    def default_rootfs_dir(cls, v: str) -> str:
        if v:
            if v.startswith("./"):
                return str((_REPO_ROOT / v.removeprefix("./")).resolve())
            return v
        return str((_REPO_ROOT / "data" / "rootfs").resolve())

    @property
    def fsems_user(self) -> str:
        import os

        return self.FSEMS_USER or os.environ.get("USER", "root")

    @property
    def workspace_path(self) -> Path:
        return Path(self.FSEMS_WORKSPACE).resolve()

    @property
    def kernels_path(self) -> Path:
        return Path(self.FSEMS_KERNELS_DIR).resolve()

    @property
    def rootfs_path(self) -> Path:
        return Path(self.FSEMS_ROOTFS_DIR).resolve()

    def offline_mount_path(self, instance_id: str) -> Path:
        return (Path(self.FSEMS_MNT_DIR) / instance_id).resolve()

    def ensure_dirs(self) -> None:
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        Path(self.FSEMS_MNT_DIR).mkdir(parents=True, exist_ok=True)
        self.kernels_path.mkdir(parents=True, exist_ok=True)
        self.rootfs_path.mkdir(parents=True, exist_ok=True)
        db_path = self.database_path
        if db_path:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        Path(self.LOGS_DIR).mkdir(parents=True, exist_ok=True)

    @property
    def database_path(self) -> Path | None:
        url = self.DATABASE_URL
        if url.startswith("sqlite+aiosqlite:///"):
            raw = url.removeprefix("sqlite+aiosqlite:///")
            return Path(raw)
        return None


@lru_cache
def get_settings() -> Settings:
    """读取 .env 后合并 data/settings.override.json 中的可编辑覆盖。"""
    base = Settings()
    try:
        from app.core.settings_store import load_overrides

        overrides = load_overrides()
    except Exception:
        overrides = {}
    if not overrides:
        return base
    # 仅应用 Settings 已声明的字段
    known = set(Settings.model_fields.keys())
    clean = {k: v for k, v in overrides.items() if k in known}
    if not clean:
        return base
    return base.model_copy(update=clean)


def reload_settings() -> Settings:
    """保存设置后清除缓存并重新加载。"""
    get_settings.cache_clear()
    return get_settings()
