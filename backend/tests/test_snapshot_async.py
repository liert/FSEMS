import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.instance import Instance
from app.services.snapshot_service import queue_create_snapshot


@pytest.mark.asyncio
async def test_queue_create_snapshot_enqueues_task(monkeypatch, tmp_path):
    from app.core.config import Settings
    from app.services import snapshot_service

    ws = tmp_path / "workspace"
    inst_dir = ws / "inst_1"
    inst_dir.mkdir(parents=True)
    drive = inst_dir / "rootfs.img"
    drive.write_bytes(b"x" * 1024)

    settings = Settings(
        FSEMS_WORKSPACE=str(ws),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    monkeypatch.setattr(snapshot_service, "get_settings", lambda: settings)

    instance = Instance(id="inst_1", name="t", template_id=1, status="STOPPED")
    session = AsyncMock()
    session.commit = AsyncMock()

    mock_delay = MagicMock()
    with patch("app.tasks.snapshot_ops.run_snapshot_create") as mock_task:
        mock_task.delay = mock_delay
        with patch.object(snapshot_service, "release_offline_mount", AsyncMock()):
            task_id, snapshot_id = await queue_create_snapshot(session, instance, "backup")

    assert task_id.startswith("task_")
    assert snapshot_id.startswith("snap_")
    session.add.assert_called_once()
    session.commit.assert_awaited()
    mock_delay.assert_called_once()
