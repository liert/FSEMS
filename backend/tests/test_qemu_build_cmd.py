import pytest

from app.services.qemu_manager import block_device_arg, net_device_arg


@pytest.mark.parametrize(
    "machine,expected",
    [
        ("virt", "virtio-blk-device,drive=hd"),
        ("malta", "virtio-blk-pci,drive=hd"),
        ("pc", "virtio-blk-pci,drive=hd"),
    ],
)
def test_block_device_arg(machine, expected):
    assert block_device_arg(machine) == expected


def test_net_device_arg():
    assert net_device_arg("malta") == "virtio-net-pci,netdev=net0"
