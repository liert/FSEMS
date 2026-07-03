from app.tasks.file_transfer import _progress_from_bytes


def test_progress_from_bytes_with_total():
    assert _progress_from_bytes(500, 1000) == 50
    assert _progress_from_bytes(1000, 1000) == 99


def test_progress_from_bytes_without_total():
    assert _progress_from_bytes(0, None) == 5
    assert _progress_from_bytes(1024 * 1024, None) >= 6
