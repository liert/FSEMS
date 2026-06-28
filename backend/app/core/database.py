from collections.abc import AsyncGenerator

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.base import Base
from app.models import instance, task, template  # noqa: F401
from app.models.template import Template

settings = get_settings()
settings.ensure_dirs()

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


SEED_TEMPLATES = [
    {
        "name": "OpenWrt 25.12.4 (ARMv8)",
        "arch": "aarch64",
        "qemu_binary": "qemu-system-aarch64",
        "machine": "virt",
        "cpu": "cortex-a72",
        "kernel_path": str((settings.workspace_path.parent / "kernels" / "openwrt-25.12.4-armsr-armv8-generic-kernel.bin").resolve()),
        "drive_path": str((settings.workspace_path.parent / "images" / "openwrt-25.12.4-armsr-armv8-generic-ext4-rootfs.img").resolve()),
        "kernel_append": "root=/dev/vda rootfstype=ext4 console=ttyAMA0",
        "ram_size": 512,
        "guest_ssh_host": "192.168.1.1",
        "guest_ssh_port": 22,
        "extra_args": "",
    },
    {
        "name": "OpenWrt Snapshot (ARMv8 Glibc)",
        "arch": "aarch64",
        "qemu_binary": "qemu-system-aarch64",
        "machine": "virt",
        "cpu": "cortex-a72",
        "kernel_path": str((settings.workspace_path.parent / "kernels" / "openwrt-snapshot-armsr-armv8-generic-kernel.bin").resolve()),
        "drive_path": str((settings.workspace_path.parent / "images" / "openwrt-snapshot-armsr-armv8-generic-ext4-rootfs.img").resolve()),
        "kernel_append": "root=/dev/vda rootfstype=ext4 console=ttyAMA0",
        "ram_size": 512,
        "guest_ssh_host": "192.168.1.1",
        "guest_ssh_port": 22,
        "extra_args": "",
    }
]


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        # 清除旧模版数据，确保版本/架构模板更新生效
        from sqlalchemy import delete
        await session.execute(delete(Template))
        await session.commit()

        # 批量添加种子模板
        for item in SEED_TEMPLATES:
            session.add(Template(**item))
        await session.commit()
