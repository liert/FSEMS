from app.services.guest_fs_offline import _parse_debugfs_ls_line


def test_parse_debugfs_ls_skips_dot_entries():
    assert _parse_debugfs_ls_line("    11   40755 (2)      0      0    4096 29-Jun-2025 15:00 .") is None
    assert _parse_debugfs_ls_line("    11   40755 (2)      0      0    4096 29-Jun-2025 15:00 ..") is None


def test_parse_debugfs_ls_directory():
    parsed = _parse_debugfs_ls_line(
        "  5794   40755 (2)      0      0    4096 29-Jun-2025 15:00 bin"
    )
    assert parsed == ("bin", True, 4096)


def test_parse_debugfs_ls_file():
    parsed = _parse_debugfs_ls_line(
        "  5793  100644 (1)      0      0     104 29-Jun-2025 15:00 VERSION"
    )
    assert parsed == ("VERSION", False, 104)


def test_parse_debugfs_ls_symlink_uses_name_only():
    parsed = _parse_debugfs_ls_line(
        "    11  120777 (7)      0      0       0 29-Jun-2025 15:00 lib -> usr/lib"
    )
    assert parsed == ("lib", False, 0)
