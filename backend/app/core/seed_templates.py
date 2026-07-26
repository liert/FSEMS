# -*- coding: utf-8 -*-
"""内置固件模板 seed 定义（按 name 幂等写入数据库）。"""
from __future__ import annotations

from pathlib import Path

from app.core.config import Settings


def _firmware_path(settings: Settings, subdir: str, filename: str) -> str:
    root = settings.kernels_path if subdir == "kernels" else settings.rootfs_path
    return str((root / filename).resolve())


def build_seed_templates(settings: Settings) -> list[dict]:
    k = lambda name: _firmware_path(settings, "kernels", name)
    r = lambda name: _firmware_path(settings, "rootfs", name)

    return [
        {
            "name": "OpenWrt 25.12.4 (ARMv8)",
            "arch": "aarch64",
            "qemu_binary": "qemu-system-aarch64",
            "machine": "virt",
            "cpu": "cortex-a72",
            "kernel_path": k("openwrt-25.12.4-armsr-armv8-generic-kernel.bin"),
            "drive_path": r("openwrt-25.12.4-armsr-armv8-generic-ext4-rootfs.img.gz"),
            "kernel_append": "root=/dev/vda rootfstype=ext4 console=ttyAMA0",
            "ram_size": 512,
            "guest_ssh_host": "192.168.1.1",
            "guest_ssh_port": 22,
            "extra_args": "",
        },
        {
            "name": "OpenWrt Snapshot (ARMv8 Glibc)",
            "arch": "aarch64",
            "qemu_binary": "qemu-system-aarch64",
            "machine": "virt",
            "cpu": "cortex-a72",
            "kernel_path": k("openwrt-snapshot-armsr-armv8-generic-kernel.bin"),
            "drive_path": r("openwrt-snapshot-armsr-armv8-generic-ext4-rootfs.img.gz"),
            "kernel_append": "root=/dev/vda rootfstype=ext4 console=ttyAMA0",
            "ram_size": 512,
            "guest_ssh_host": "192.168.1.1",
            "guest_ssh_port": 22,
            "extra_args": "",
        },
        {
            "name": "OpenWrt MIPS (malta)",
            "arch": "mips",
            "qemu_binary": "qemu-system-mips",
            "machine": "malta",
            "cpu": "24Kf",
            "kernel_path": k("openwrt-malta-be-generic-kernel.bin"),
            "drive_path": r("openwrt-malta-be-generic-ext4-rootfs.img.gz"),
            "kernel_append": "root=/dev/sda rootfstype=ext4 rootwait console=ttyS0,38400n8",
            "ram_size": 256,
            "guest_ssh_host": "192.168.1.1",
            "guest_ssh_port": 22,
            "extra_args": "",
        },
        {
            "name": "OpenWrt MIPSEL (malta)",
            "arch": "mipsel",
            "qemu_binary": "qemu-system-mipsel",
            "machine": "malta",
            "cpu": "24Kc",
            "kernel_path": k("openwrt-mipsel-malta-vmlinux.bin"),
            "drive_path": r("openwrt-mipsel-malta-rootfs.img.gz"),
            "kernel_append": "root=/dev/sda rootfstype=ext4 rootwait console=ttyS0,38400n8",
            "ram_size": 256,
            "guest_ssh_host": "192.168.1.1",
            "guest_ssh_port": 22,
            "extra_args": "",
        },
        {
            "name": "OpenWrt x86_64 (PC)",
            "arch": "x86_64",
            "qemu_binary": "qemu-system-x86_64",
            "machine": "pc",
            "cpu": "qemu64",
            "kernel_path": k("openwrt-x86-64-vmlinuz"),
            "drive_path": r("openwrt-x86-64-rootfs.img.gz"),
            "kernel_append": "root=/dev/vda rootfstype=ext4 console=ttyS0",
            "ram_size": 512,
            "guest_ssh_host": "192.168.1.1",
            "guest_ssh_port": 22,
            "extra_args": "",
        },
    ]


def seed_template_names() -> list[str]:
    """不依赖 Settings 的静态名称列表（测试用）。"""
    from app.core.config import get_settings

    return [t["name"] for t in build_seed_templates(get_settings())]
