from app.services.guest_fs_offline import (
    _parse_debugfs_ls_line,
    _resolve_link_target,
    _enrich_debugfs_symlink_dirs,
)


def test_parse_debugfs_ls_skips_dot_entries():
    assert _parse_debugfs_ls_line("    11   40755 (2)      0      0    4096 29-Jun-2025 15:00 .") is None
    assert _parse_debugfs_ls_line("    11   40755 (2)      0      0    4096 29-Jun-2025 15:00 ..") is None


def test_parse_debugfs_ls_directory():
    parsed = _parse_debugfs_ls_line(
        "  5794   40755 (2)      0      0    4096 29-Jun-2025 15:00 bin"
    )
    assert parsed is not None
    name, is_dir, size, mtime, is_link, link_target = parsed
    assert name == "bin"
    assert is_dir is True
    assert is_link is False
    assert link_target is None
    assert size == 4096
    assert mtime > 0


def test_parse_debugfs_ls_file():
    parsed = _parse_debugfs_ls_line(
        "  5793  100644 (1)      0      0     104 29-Jun-2025 15:00 VERSION"
    )
    assert parsed is not None
    name, is_dir, size, mtime, is_link, _ = parsed
    assert name == "VERSION"
    assert is_dir is False
    assert is_link is False
    assert size == 104
    assert mtime > 0


def test_parse_debugfs_ls_symlink():
    parsed = _parse_debugfs_ls_line(
        "    11  120777 (7)      0      0       0 29-Jun-2025 15:00 lib -> usr/lib"
    )
    assert parsed is not None
    name, is_dir, size, mtime, is_link, link_target = parsed
    assert name == "lib"
    assert is_dir is False  # 原始类型是链接，是否目录由 enrich 判定
    assert is_link is True
    assert link_target == "usr/lib"
    assert size == 0


def test_parse_debugfs_ls_lost_found_is_dir():
    """回归：mode 必须以八进制解析，否则目录会被当成文件显示 4KB。"""
    parsed = _parse_debugfs_ls_line(
        "     11   40700 (2)      0      0    4096  1-Jan-1970 08:00 lost+found"
    )
    assert parsed is not None
    name, is_dir, size, _mtime, is_link, _ = parsed
    assert name == "lost+found"
    assert is_dir is True
    assert is_link is False


def test_resolve_link_target_relative_and_absolute():
    assert _resolve_link_target("/", "usr/lib") == "/usr/lib"
    assert _resolve_link_target("/usr", "lib") == "/usr/lib"
    assert _resolve_link_target("/var", "/tmp") == "/tmp"


def test_enrich_symlink_dirs_marks_link_to_dir():
    """lib -> usr/lib 且 usr 下有 lib 目录时，lib 应标为可进入目录。"""
    entries = [
        {
            "name": "lib",
            "path": "/lib",
            "is_dir": False,
            "size": 0,
            "mtime": 0,
            "is_link": True,
            "link_target": "usr/lib",
        }
    ]

    def fake_is_dir(drive, path, depth=0):
        return path in {"/usr/lib", "/usr"}

    # 直接测 resolve + 逻辑：用 monkeypatch 在调用处
    from app.services import guest_fs_offline as mod

    original = mod._debugfs_path_is_dir
    mod._debugfs_path_is_dir = lambda drive, path, depth=0: path == "/usr/lib"
    try:
        _enrich_debugfs_symlink_dirs(None, "/", entries)  # type: ignore[arg-type]
        assert entries[0]["is_dir"] is True
        assert entries[0]["size"] == 0
    finally:
        mod._debugfs_path_is_dir = original
