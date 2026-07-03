# -*- coding: utf-8 -*-
import logging
import os
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_process_rss_mb(pid: int | None) -> float | None:
    if not pid or pid <= 0:
        return None
    status_path = Path(f"/proc/{pid}/status")
    if not status_path.is_file():
        return None
    try:
        for line in status_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmRSS:"):
                kb = int(line.split()[1])
                return round(kb / 1024, 1)
    except OSError as exc:
        logger.debug("读取进程内存失败 pid=%s: %s", pid, exc)
    return None


def _parse_debugfs_stats(output: str) -> tuple[int | None, int | None]:
    block_count: int | None = None
    free_blocks: int | None = None
    block_size = 4096
    fs_size_bytes: int | None = None

    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Filesystem size:"):
            match = re.search(r"Filesystem size:\s+(\d+)", stripped)
            if match:
                fs_size_bytes = int(match.group(1))
        elif stripped.startswith("Block count:"):
            block_count = int(stripped.split(":", 1)[1].strip().split()[0])
        elif stripped.startswith("Free blocks:"):
            free_blocks = int(stripped.split(":", 1)[1].strip().split()[0])
        elif stripped.startswith("Block size:"):
            block_size = int(stripped.split(":", 1)[1].strip().split()[0])

    if block_count is not None and free_blocks is not None:
        total = block_count * block_size
        used = (block_count - free_blocks) * block_size
        return total, max(used, 0)

    if fs_size_bytes is not None and free_blocks is not None and block_size > 0:
        total_blocks = fs_size_bytes // block_size
        used = (total_blocks - free_blocks) * block_size
        return fs_size_bytes, max(used, 0)

    return None, None


def get_ext4_filesystem_stats(path: Path) -> tuple[int | None, int | None]:
    """读取 raw ext4 镜像内文件系统的 (总容量 bytes, 已用 bytes)。"""
    if not path.is_file():
        return None, None
    try:
        proc = subprocess.run(
            ["debugfs", "-R", "stats", str(path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if proc.returncode != 0:
            logger.debug("debugfs stats 失败 %s: %s", path, proc.stderr.strip())
            return None, None
        total, used = _parse_debugfs_stats(proc.stdout)
        if total is not None:
            return total, used
        logger.debug("无法解析 debugfs stats 输出: %s", path)
    except Exception as exc:
        logger.debug("debugfs stats 异常 %s: %s", path, exc)
    return None, None


def get_disk_image_stats(path: Path) -> tuple[int | None, int | None]:
    """返回 ext4 文件系统 (总容量 bytes, 已用 bytes)；失败时回退为镜像文件大小。"""
    total, used = get_ext4_filesystem_stats(path)
    if total is not None:
        return total, used
    try:
        size = path.stat().st_size
        return size, None
    except OSError:
        return None, None


def expand_drive_image(path: Path, expand_mb: int) -> tuple[int | None, int | None]:
    """扩容 raw ext4 镜像并扩展文件系统，返回扩容后的 (总容量, 已用)。"""
    if expand_mb <= 0:
        raise ValueError("expand_mb must be positive")

    before_total, _ = get_ext4_filesystem_stats(path)

    subprocess.run(
        ["e2fsck", "-f", "-y", str(path)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )

    resize_img = subprocess.run(
        ["qemu-img", "resize", str(path), f"+{expand_mb}M"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if resize_img.returncode != 0:
        err = (resize_img.stderr or resize_img.stdout or "qemu-img resize failed").strip()
        raise RuntimeError(err)

    resize_fs = subprocess.run(
        ["resize2fs", str(path)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if resize_fs.returncode != 0:
        err = (resize_fs.stderr or resize_fs.stdout or "resize2fs failed").strip()
        raise RuntimeError(err)

    after_total, after_used = get_ext4_filesystem_stats(path)
    if before_total and after_total and after_total <= before_total:
        raise RuntimeError("扩容后文件系统容量未增长，请检查 e2fsprogs / qemu-img 是否可用")
    return after_total, after_used


def get_path_size_bytes(path: Path) -> int | None:
    if not path.exists():
        return None
    if path.is_file():
        try:
            return path.stat().st_size
        except OSError:
            return None
    total = 0
    try:
        for root, _dirs, files in os.walk(path, followlinks=False):
            for name in files:
                try:
                    total += (Path(root) / name).stat(follow_symlinks=False).st_size
                except OSError:
                    continue
    except OSError as exc:
        logger.debug("统计目录大小失败 %s: %s", path, exc)
        return None
    return total
