from collections.abc import AsyncGenerator

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.base import Base
from app.models import instance, snapshot, task, template  # noqa: F401
from app.core.seed_templates import build_seed_templates
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


async def init_db() -> None:
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE instances ADD COLUMN network_type VARCHAR(20) DEFAULT 'same'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE instances ADD COLUMN bridge_name VARCHAR(50) DEFAULT 'br_fsems'"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE instances ADD COLUMN custom_rootfs_path VARCHAR(512)"))
        except Exception:
            pass
        try:
            await conn.execute(
                text("ALTER TABLE instances ADD COLUMN filesystem_type VARCHAR(20) DEFAULT 'ext4'")
            )
        except Exception:
            pass
        try:
            await conn.execute(
                text("ALTER TABLE instances ADD COLUMN use_custom_rootfs BOOLEAN NOT NULL DEFAULT 0")
            )
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE tasks ADD COLUMN result_ref VARCHAR(50)"))
        except Exception:
            pass

    async with SessionLocal() as session:
        await _seed_templates(session)


async def _seed_templates(session: AsyncSession) -> None:
    """按 name 幂等写入种子模板：保留已有 id，避免破坏实例外键。"""
    result = await session.execute(select(Template))
    existing_by_name = {t.name: t for t in result.scalars().all()}

    updatable_fields = (
        "arch",
        "qemu_binary",
        "machine",
        "cpu",
        "kernel_path",
        "drive_path",
        "kernel_append",
        "ram_size",
        "guest_ssh_host",
        "guest_ssh_port",
        "extra_args",
    )

    for item in build_seed_templates(settings):
        name = item["name"]
        if name in existing_by_name:
            tpl = existing_by_name[name]
            for field in updatable_fields:
                setattr(tpl, field, item[field])
        else:
            session.add(Template(**item))

    await session.commit()
