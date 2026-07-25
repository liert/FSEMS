from app.services.guest_fs_offline import _parse_debugfs_ls_line


def test_parse_debugfs_ls_skips_dot_entries():
    assert _parse_debugfs_ls_line("    11   40755 (2)      0      0    4096 29-Jun-2025 15:00 .") is None
    assert _parse_debugfs_ls_line("    11   40755 (2)      0      0    4096 29-Jun-2025 15:00 ..") is None


def test_parse_debugfs_ls_directory():
    parsed = _parse_debugfs_ls_line(
        "  5794   40755 (2)      0      0    4096 29-Jun-2025 15:00 bin"
    )
    assert parsed is not None
    name, is_dir, size, mtime = parsed
    assert name == "bin"
    assert is_dir is True
    assert size == 4096
    assert mtime > 0


def test_parse_debugfs_ls_file():
    parsed = _parse_debugfs_ls_line(
        "  5793  100644 (1)      0      0     104 29-Jun-2025 15:00 VERSION"
    )
    assert parsed is not None
    name, is_dir, size, mtime = parsed
    assert name == "VERSION"
    assert is_dir is False
    assert size == 104
    assert mtime > 0


def test_parse_debugfs_ls_symlink_is_not_dir():
    parsed = _parse_debugfs_ls_line(
        "    11  120777 (7)      0      0       0 29-Jun-2025 15:00 lib -> usr/lib"
    )
    assert parsed is not None
    name, is_dir, size, mtime = parsed
    assert name == "lib"
    assert is_dir is False
    assert size == 0


def test_parse_debugfs_ls_lost_found_is_dir():
    """回归：mode 必须以八进制解析，否则目录会被当成文件显示 4KB。"""
    parsed = _parse_debugfs_ls_line(
        "     11   40700 (2)      0      0    4096  1-Jan-1970 08:00 lost+found"
    )
    assert parsed is not None
    name, is_dir, size, _mtime = parsed
    assert name == "lost+found"
    assert is_dir is True
