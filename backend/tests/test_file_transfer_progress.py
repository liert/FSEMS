from pathlib import Path

import pytest

from app.tasks import file_transfer
from app.tasks.file_transfer import _dependency_search_root, _progress_from_bytes


def test_progress_from_bytes_with_total():
    assert _progress_from_bytes(500, 1000) == 50
    assert _progress_from_bytes(1000, 1000) == 99


def test_progress_from_bytes_without_total():
    assert _progress_from_bytes(0, None) == 5
    assert _progress_from_bytes(1024 * 1024, None) >= 6


def test_dependency_search_root_uses_instance_root_for_source_inside(tmp_path, monkeypatch):
    rootfs = tmp_path / "inst_test" / "rootfs"
    source = rootfs / "usr" / "bin" / "demo"
    source.parent.mkdir(parents=True)
    source.touch()

    monkeypatch.setattr(file_transfer, "resolve_instance_host_root", lambda instance_id: rootfs)

    assert _dependency_search_root("inst_test", str(source)) == rootfs


def test_dependency_search_root_falls_back_to_source_parent(tmp_path, monkeypatch):
    rootfs = tmp_path / "inst_test" / "rootfs"
    rootfs.mkdir(parents=True)
    source = tmp_path / "uploads" / "demo"
    source.parent.mkdir(parents=True)
    source.touch()

    monkeypatch.setattr(file_transfer, "resolve_instance_host_root", lambda instance_id: rootfs)

    assert _dependency_search_root("inst_test", str(source)) == source.parent


@pytest.mark.asyncio
async def test_host_to_guest_uses_provided_search_root(monkeypatch, caplog):
    calls = {}

    async def fake_set_progress(task_id, progress, status=None):
        pass

    async def fake_push(src, host, dest, *, port, search_root, progress, on_line):
        calls["search_root"] = search_root
        calls["on_line"] = on_line
        on_line("/tmp/rootfs/usr/lib/libdbus-1.so.3 -> root@192.168.1.4:/usr/lib/libdbus-1.so.3")

    monkeypatch.setattr(file_transfer, "_set_task_progress", fake_set_progress)
    monkeypatch.setattr(file_transfer.iot_tools_client, "scp_host_to_guest", fake_push)

    with caplog.at_level("INFO", logger="app.tasks.file_transfer"):
        await file_transfer._transfer_via_iot_tools(
            "host_to_guest",
            "/tmp/src",
            "/usr/bin/src",
            host="192.168.1.4",
            port=22,
            task_id="task_test",
            search_root=Path("/tmp/rootfs"),
        )

    assert calls["search_root"] == Path("/tmp/rootfs")
    assert calls["on_line"] is not None
    assert "[task=task_test] iot-tools | /tmp/rootfs/usr/lib/libdbus-1.so.3" in caplog.text
