import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services import firmware_tools


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        FSEMS_WORKSPACE=str(tmp_path / "workspace"),
        FSEMS_ROOTFS_DIR=str(tmp_path / "rootfs"),
        FSEMS_KERNELS_DIR=str(tmp_path / "kernels"),
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
    )


def test_resolve_source_path_accepts_any_regular_file(tmp_path, monkeypatch):
    monkeypatch.setattr(firmware_tools, "get_settings", lambda: _settings(tmp_path))
    outside = tmp_path / "outside.img"
    outside.write_bytes(b"not-an-image")

    assert firmware_tools.resolve_source_path(str(outside)) == outside.resolve()


def test_resolve_source_path_rejects_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(firmware_tools, "get_settings", lambda: _settings(tmp_path))
    directory = tmp_path / "not-an-image"
    directory.mkdir()

    with pytest.raises(HTTPException, match="普通文件"):
        firmware_tools.resolve_source_path(str(directory))


def test_detect_and_convert_ext4_to_squashfs(tmp_path, monkeypatch):
    settings = _settings(tmp_path)
    monkeypatch.setattr(firmware_tools, "get_settings", lambda: settings)
    tree = tmp_path / "tree"
    (tree / "etc").mkdir(parents=True)
    (tree / "etc" / "banner").write_text("FSEMS")
    source = Path(settings.FSEMS_ROOTFS_DIR) / "source.img"
    source.parent.mkdir(parents=True)
    subprocess.run(["truncate", "-s", "32M", str(source)], check=True)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-d", str(tree), str(source)], check=True)

    assert firmware_tools.detect_filesystem(source) == "ext4"
    result = firmware_tools.convert_filesystem(str(source), "auto", "squashfs")

    output = Path(result["output_path"])
    assert output.is_file()
    assert result["source_type"] == "ext4"
    assert result["target_type"] == "squashfs"
    assert firmware_tools.detect_filesystem(output) == "squashfs"
