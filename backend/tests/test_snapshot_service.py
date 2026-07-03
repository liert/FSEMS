import pytest
from fastapi import HTTPException

from app.models.instance import Instance
from app.services.snapshot_service import _require_stopped, instance_drive_path, snapshots_dir


def test_require_stopped_rejects_running():
    instance = Instance(
        id="inst_test",
        name="t",
        template_id=1,
        status="RUNNING",
    )
    with pytest.raises(HTTPException) as exc:
        _require_stopped(instance)
    assert exc.value.status_code == 409


def test_snapshots_dir_under_workspace(tmp_path, monkeypatch):
    from app.core.config import Settings
    from app.services import snapshot_service

    settings = Settings(
        FSEMS_WORKSPACE=str(tmp_path / "workspace"),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    monkeypatch.setattr(snapshot_service, "get_settings", lambda: settings)
    path = snapshots_dir("inst_abc")
    assert path == (tmp_path / "workspace" / "inst_abc" / "snapshots").resolve()


def test_instance_drive_path_prefers_instance_field(tmp_path, monkeypatch):
    from app.core.config import Settings
    from app.services import snapshot_service

    ws = tmp_path / "workspace"
    (ws / "inst_x").mkdir(parents=True)
    drive = ws / "inst_x" / "rootfs.img"
    drive.write_bytes(b"img")

    settings = Settings(
        FSEMS_WORKSPACE=str(ws),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    monkeypatch.setattr(snapshot_service, "get_settings", lambda: settings)

    instance = Instance(id="inst_x", name="t", template_id=1, drive_path=str(drive))
    assert instance_drive_path(instance) == drive
