import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import host_fs


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "hello.txt").write_text("hi")
    settings = Settings(
        FSEMS_WORKSPACE=str(ws),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )
    monkeypatch.setattr(host_fs, "get_settings", lambda: settings)
    return ws


def test_resolve_relative_path_inside_workspace(workspace):
    path = host_fs.resolve_workspace_path("hello.txt")
    assert path.name == "hello.txt"
    assert path.read_text() == "hi"


def test_resolve_empty_path_returns_workspace_root(workspace):
    path = host_fs.resolve_workspace_path("")
    assert path == workspace.resolve()


def test_reject_path_outside_workspace(workspace):
    outside = workspace.parent / "outside.txt"
    outside.write_text("secret")
    with pytest.raises(HTTPException) as exc:
        host_fs.resolve_workspace_path(str(outside))
    assert exc.value.status_code == 404
    detail = exc.value.detail
    assert detail["error_code"] == "FS_PATH_NOT_FOUND"


def test_reject_missing_path(workspace):
    with pytest.raises(HTTPException) as exc:
        host_fs.resolve_workspace_path("missing.txt")
    assert exc.value.status_code == 404


def test_resolve_workspace_entry_preserves_symlink(workspace):
    real = workspace / "lib" / "libdemo.so.1"
    real.parent.mkdir()
    real.write_text("demo")
    link = workspace / "usr" / "lib" / "libdemo.so"
    link.parent.mkdir(parents=True)
    link.symlink_to(real)

    resolved = host_fs.resolve_workspace_entry(str(link))

    assert resolved == link
    assert resolved.is_symlink()
    assert resolved.read_text() == "demo"


def test_resolve_workspace_entry_rejects_broken_symlink(workspace):
    link = workspace / "broken.so"
    link.symlink_to("missing.so")

    with pytest.raises(HTTPException) as exc:
        host_fs.resolve_workspace_entry(str(link))
    assert exc.value.status_code == 404
    assert exc.value.detail["error_code"] == "FS_PATH_NOT_FOUND"
