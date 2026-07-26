import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.database import _seed_templates
from app.core.seed_templates import build_seed_templates
from app.models import instance, snapshot, task, template  # noqa: F401
from app.models.base import Base
from app.models.template import Template


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def seed_templates():
    settings = Settings(
        FSEMS_WORKSPACE="/tmp/fsems-test/workspace",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    return build_seed_templates(settings)


@pytest.mark.asyncio
async def test_seed_templates_idempotent(db_session, monkeypatch):
    settings = Settings(
        FSEMS_WORKSPACE="/tmp/fsems-test/workspace",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    expected = build_seed_templates(settings)
    monkeypatch.setattr("app.core.database.settings", settings)

    await _seed_templates(db_session)
    first = (await db_session.execute(select(Template).order_by(Template.id))).scalars().all()
    assert len(first) == len(expected)
    first_ids = [t.id for t in first]

    await _seed_templates(db_session)
    second = (await db_session.execute(select(Template).order_by(Template.id))).scalars().all()
    assert [t.id for t in second] == first_ids
    assert len(second) == len(expected)

    by_name = {t.name: t for t in second}
    for item in expected:
        assert item["name"] in by_name
        assert by_name[item["name"]].arch == item["arch"]


def test_build_seed_templates_includes_multi_arch(seed_templates):
    archs = {t["arch"] for t in seed_templates}
    assert archs >= {"aarch64", "mips", "mipsel", "x86_64"}
    assert len(seed_templates) >= 5


def test_mips_seed_uses_configured_firmware_dirs_and_malta_devices():
    settings = Settings(
        FSEMS_WORKSPACE="/tmp/fsems-test/workspace",
        FSEMS_KERNELS_DIR="/opt/fsems/kernels",
        FSEMS_ROOTFS_DIR="/opt/fsems/rootfs",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    templates = build_seed_templates(settings)
    mips = next(t for t in templates if t["name"] == "OpenWrt MIPS (malta)")

    assert mips["cpu"] == "24Kf"
    assert mips["kernel_path"] == "/opt/fsems/kernels/openwrt-malta-be-generic-kernel.bin"
    assert mips["drive_path"] == "/opt/fsems/rootfs/openwrt-malta-be-generic-ext4-rootfs.img.gz"
    assert mips["kernel_append"] == (
        "root=/dev/sda rootfstype=ext4 rootwait console=ttyS0,38400n8"
    )
