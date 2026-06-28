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
    LOGS_DIR: str = ""

    FSEMS_BRIDGE: str = "br_fsems"
    QEMU_SERIAL_DIR: str = "/tmp"
    BOOT_TIMEOUT_SEC: int = 120
    FSEMS_USER: str = ""

    FSEMS_GUEST_SSH_USER: str = "root"
    FSEMS_GUEST_SSH_PASSWORD: str = ""

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

    @property
    def fsems_user(self) -> str:
        import os

        return self.FSEMS_USER or os.environ.get("USER", "root")

    @property
    def workspace_path(self) -> Path:
        return Path(self.FSEMS_WORKSPACE).resolve()

    def ensure_dirs(self) -> None:
        self.workspace_path.mkdir(parents=True, exist_ok=True)
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
    return Settings()
