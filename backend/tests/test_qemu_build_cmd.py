from types import SimpleNamespace

import pytest

from app.services.qemu_manager import (
    block_device_arg,
    build_cmd,
    effective_kernel_append,
    net_device_arg,
)


@pytest.mark.parametrize(
    "machine,expected",
    [
        ("virt", "virtio-blk-device,drive=hd"),
        ("malta", None),
        ("pc", "virtio-blk-pci,drive=hd"),
    ],
)
def test_block_device_arg(machine, expected):
    assert block_device_arg(machine) == expected


def test_net_device_arg():
    assert net_device_arg("malta") == "pcnet,netdev=net0"
    assert net_device_arg("virt") == "virtio-net-pci,netdev=net0"


def test_malta_kernel_append_is_corrected():
    template = SimpleNamespace(
        machine="malta",
        kernel_append="root=/dev/vda rootfstype=ext4 console=ttyAMA0",
    )
    assert effective_kernel_append(template) == (
        "root=/dev/sda rootfstype=ext4 console=ttyS0,38400n8 rootwait"
    )


def test_filesystem_type_overrides_template_kernel_append():
    template = SimpleNamespace(
        machine="virt",
        kernel_append="root=/dev/vda rootfstype=ext4 console=ttyAMA0",
    )
    assert effective_kernel_append(template, "squashfs") == (
        "root=/dev/vda rootfstype=squashfs console=ttyAMA0"
    )


def test_malta_build_cmd_uses_ide_pcnet_and_ttys0(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.qemu_manager.serial_socket_path",
        lambda instance_id: str(tmp_path / f"{instance_id}.sock"),
    )
    instance = SimpleNamespace(
        id="inst_test",
        drive_path=str(tmp_path / "rootfs.img"),
        serial_socket=None,
        tap_name="tap_test",
    )
    template = SimpleNamespace(
        qemu_binary="qemu-system-mips",
        machine="malta",
        cpu="24Kc",
        ram_size=256,
        kernel_path=str(tmp_path / "kernel.bin"),
        kernel_append="root=/dev/vda rootfstype=ext4 console=ttyAMA0",
        drive_path=str(tmp_path / "template.img"),
        extra_args="",
    )

    cmd = build_cmd(instance, template)
    assert "file=%s,format=raw,if=ide,index=0,media=disk" % instance.drive_path in cmd
    assert "pcnet,netdev=net0" in cmd
    assert cmd[cmd.index("-cpu") + 1] == "24Kf"
    assert "virtio-blk-pci,drive=hd" not in cmd
    assert "virtio-net-pci,netdev=net0" not in cmd
    assert cmd[cmd.index("-append") + 1] == (
        "root=/dev/sda rootfstype=ext4 console=ttyS0,38400n8 rootwait"
    )
