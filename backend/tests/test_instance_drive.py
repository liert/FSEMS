import gzip
from pathlib import Path

from app.services.instance_service import deploy_instance_drive


def test_deploy_instance_drive_decompresses_gzip(tmp_path: Path):
    source = tmp_path / "rootfs.img.gz"
    destination = tmp_path / "instance" / "rootfs.img"
    payload = b"ext4-image" * 128
    with gzip.open(source, "wb") as f:
        f.write(payload)

    deploy_instance_drive(source, destination)

    assert destination.read_bytes() == payload


def test_deploy_instance_drive_copies_raw_image(tmp_path: Path):
    source = tmp_path / "rootfs.img"
    destination = tmp_path / "instance" / "rootfs.img"
    payload = b"raw-ext4-image" * 128
    source.write_bytes(payload)

    deploy_instance_drive(source, destination)

    assert destination.read_bytes() == payload
