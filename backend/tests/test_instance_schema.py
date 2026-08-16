import pytest
from pydantic import ValidationError

from app.schemas.instance import InstanceCpuUpdate, InstanceCreate


def test_instance_create_defaults_to_ext4():
    payload = InstanceCreate(name="test", template_id=1)

    assert payload.filesystem_type == "ext4"
    assert payload.use_custom_rootfs is False


@pytest.mark.parametrize("filesystem_type", ["ext4", "squashfs", "f2fs"])
def test_instance_create_accepts_supported_filesystems(filesystem_type):
    payload = InstanceCreate(name="test", template_id=1, filesystem_type=filesystem_type)

    assert payload.filesystem_type == filesystem_type


def test_instance_create_rejects_unsupported_filesystem():
    with pytest.raises(ValidationError):
        InstanceCreate(name="test", template_id=1, filesystem_type="ubifs")


def test_instance_create_accepts_custom_rootfs_boot_flag():
    payload = InstanceCreate(
        name="test", template_id=1, rootfs_path="/tmp/rootfs.img", use_custom_rootfs=True
    )

    assert payload.use_custom_rootfs is True


def test_instance_cpu_update_accepts_null_to_restore_template_default():
    payload = InstanceCpuUpdate(cpu=None)
    assert payload.cpu is None


def test_instance_cpu_update_accepts_qemu_cpu_name():
    payload = InstanceCpuUpdate(cpu="max")
    assert payload.cpu == "max"
