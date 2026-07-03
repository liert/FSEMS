from app.services.snapshot_service import parse_qemu_img_progress


def test_parse_qemu_img_progress():
    assert parse_qemu_img_progress("    (0.00/100%)") == 0
    assert parse_qemu_img_progress("    (42.50/100%)") == 42
    assert parse_qemu_img_progress("no progress here") is None
