# -*- coding: utf-8 -*-
import asyncio
import logging
import posixpath
import re
import shutil
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.host_fs import list_directory
from app.services.network_setup import run_privileged_cmd
from app.services.ssh_service import GuestPathNotFoundError

logger = logging.getLogger(__name__)

_mount_locks: dict[str, asyncio.Lock] = {}
_DEBUGFS_LS = re.compile(
    r"^\s*\d+\s+(\d+)\s+\(\d+\)\s+\d+\s+\d+\s+(\d+)\s+.+\s+(.+)$"
)
_S_IFDIR = 0o040000


def _lock_for(instance_id: str) -> asyncio.Lock:
    if instance_id not in _mount_locks:
        _mount_locks[instance_id] = asyncio.Lock()
    return _mount_locks[instance_id]


def offline_mount_point(instance_id: str) -> Path:
    settings = get_settings()
    return settings.offline_mount_path(instance_id)


def extracted_rootfs_dir(instance_id: str) -> Path:
    settings = get_settings()
    return (settings.workspace_path / instance_id / "rootfs").resolve()


def _tool_path(name: str) -> str | None:
    return shutil.which(name)


async def _is_mounted(mount_point: Path) -> bool:
    if not mount_point.is_dir():
        return False

    mountpoint_bin = _tool_path("mountpoint")
    if mountpoint_bin:
        try:
            proc = await asyncio.create_subprocess_exec(
                mountpoint_bin,
                "-q",
                str(mount_point),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except FileNotFoundError:
            pass

    resolved = mount_point.resolve().as_posix()
    try:
        for line in Path("/proc/mounts").read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == resolved:
                return True
    except OSError:
        return False
    return False


def resolve_offline_guest_path(mount_root: Path, guest_path: str) -> Path:
    """将访客机 POSIX 路径映射到挂载点或解压目录下的宿主机路径。"""
    mount_resolved = mount_root.resolve()
    normalized = posixpath.normpath(guest_path.strip() or "/")
    if normalized == "/":
        target = mount_resolved
    else:
        relative = normalized.lstrip("/")
        target = (mount_resolved / relative).resolve()

    try:
        target.relative_to(mount_resolved)
    except ValueError as exc:
        raise GuestPathNotFoundError(
            guest_path,
            "Path outside guest root",
        ) from exc

    if not target.exists():
        raise GuestPathNotFoundError(guest_path, f"目录不存在或无法读取: {guest_path}")

    return target


def list_offline_guest_directory(mount_root: Path, guest_path: str) -> list[dict]:
    target = resolve_offline_guest_path(mount_root, guest_path)
    if not target.is_dir():
        raise GuestPathNotFoundError(guest_path, f"Not a directory: {guest_path}")

    parent_guest = posixpath.normpath(guest_path.strip() or "/")
    entries: list[dict] = []
    for item in list_directory(target):
        name = item["name"]
        if parent_guest == "/":
            entry_path = f"/{name}"
        else:
            entry_path = posixpath.join(parent_guest, name)
        entries.append(
            {
                "name": name,
                "path": entry_path,
                "is_dir": item["is_dir"],
                "size": item["size"],
                "mtime": item["mtime"],
            }
        )
    return entries


def _parse_debugfs_ls_line(line: str) -> tuple[str, bool, int] | None:
    match = _DEBUGFS_LS.match(line.strip())
    if not match:
        return None
    mode = int(match.group(1))
    size = int(match.group(2))
    name = match.group(3).strip()
    if name in (".", ".."):
        return None
    if " -> " in name:
        name = name.split(" -> ", 1)[0].strip()
    is_dir = (mode & 0o170000) == _S_IFDIR
    return name, is_dir, size


def _list_debugfs_guest_directory_sync(drive_path: Path, guest_path: str) -> list[dict]:
    debugfs_bin = _tool_path("debugfs")
    if not debugfs_bin:
        raise RuntimeError("debugfs 未安装")

    normalized = posixpath.normpath(guest_path.strip() or "/")
    debugfs_dir = normalized if normalized != "" else "/"
    cmd = [debugfs_bin, "-R", f"ls -l {debugfs_dir}", str(drive_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        lowered = output.lower()
        if "not found" in lowered or "does not exist" in lowered or "can't find" in lowered:
            raise GuestPathNotFoundError(guest_path, f"目录不存在或无法读取: {guest_path}")
        raise RuntimeError(output.strip() or "debugfs failed")

    parent_guest = normalized
    entries: list[dict] = []
    for line in output.splitlines():
        parsed = _parse_debugfs_ls_line(line)
        if not parsed:
            continue
        name, is_dir, size = parsed
        if parent_guest == "/":
            entry_path = f"/{name}"
        else:
            entry_path = posixpath.join(parent_guest, name)
        entries.append(
            {
                "name": name,
                "path": entry_path,
                "is_dir": is_dir,
                "size": size,
                "mtime": 0,
            }
        )
    return entries


async def list_guest_offline_directory(
    instance_id: str,
    drive_path: Path,
    guest_path: str,
) -> list[dict]:
    """离线列举访客机目录：优先解压目录 → debugfs → guestmount。"""
    drive_path = drive_path.resolve()
    if not drive_path.is_file():
        raise FileNotFoundError(f"Drive image not found: {drive_path}")

    extracted = extracted_rootfs_dir(instance_id)
    if extracted.is_dir() and any(extracted.iterdir()):
        logger.info("离线 VFS 使用解压目录: %s", extracted)
        return list_offline_guest_directory(extracted, guest_path)

    errors: list[str] = []

    if _tool_path("debugfs"):
        try:
            return await asyncio.to_thread(_list_debugfs_guest_directory_sync, drive_path, guest_path)
        except GuestPathNotFoundError:
            raise
        except Exception as exc:
            errors.append(f"debugfs: {exc}")
            logger.warning("debugfs 离线浏览失败: %s", exc)

    if _tool_path("guestmount"):
        try:
            mount_root = await ensure_offline_mount(instance_id, drive_path)
            return list_offline_guest_directory(mount_root, guest_path)
        except GuestPathNotFoundError:
            raise
        except Exception as exc:
            errors.append(f"guestmount: {exc}")
            logger.warning("guestmount 离线浏览失败: %s", exc)

    if errors:
        raise RuntimeError("; ".join(errors))

    raise RuntimeError(
        "离线浏览需要 debugfs（e2fsprogs）或 guestmount（libguestfs-tools）。"
        "请参考 README.md 安装相应系统依赖包。"
    )


async def ensure_offline_mount(instance_id: str, drive_path: Path) -> Path:
    """只读 guestmount；与 RUNNING 的 QEMU 互斥，由调用方保证实例已停止。"""
    if not drive_path.is_file():
        raise FileNotFoundError(f"Drive image not found: {drive_path}")

    guestmount_bin = _tool_path("guestmount")
    if not guestmount_bin:
        raise RuntimeError(
            "guestmount 未安装。请参考 README.md 安装 libguestfs-tools 依赖包。"
        )

    mount_point = offline_mount_point(instance_id)
    mount_point.parent.mkdir(parents=True, exist_ok=True)

    async with _lock_for(instance_id):
        if await _is_mounted(mount_point):
            return mount_point

        mount_point.mkdir(parents=True, exist_ok=True)

        # OpenWrt rootfs.img 多为 raw ext4；--inspect 自动探测分区，-m 覆盖常见布局
        attempts = [
            [guestmount_bin, "-a", str(drive_path), "--inspect", "--ro", str(mount_point)],
            [guestmount_bin, "-a", str(drive_path), "-m", "/dev/sda", "--ro", str(mount_point)],
            [guestmount_bin, "-a", str(drive_path), "-m", "/dev/sda1", "--ro", str(mount_point)],
            [guestmount_bin, "-a", str(drive_path), "-m", "/dev/vda1", "--ro", str(mount_point)],
        ]
        last_error = ""
        for cmd in attempts:
            try:
                await run_privileged_cmd(cmd, check=True)
                if await _is_mounted(mount_point):
                    logger.info("离线 VFS 挂载成功: %s -> %s", drive_path, mount_point)
                    return mount_point
                last_error = "guestmount completed but mountpoint check failed"
            except Exception as exc:
                last_error = str(exc)
                logger.warning("guestmount 尝试失败 (%s): %s", " ".join(cmd), exc)

        raise RuntimeError(last_error or "guestmount failed")


async def release_offline_mount(instance_id: str) -> None:
    mount_point = offline_mount_point(instance_id)

    async with _lock_for(instance_id):
        if not mount_point.exists() and not await _is_mounted(mount_point):
            return

        guestunmount_bin = _tool_path("guestunmount")
        fusermount_bin = _tool_path("fusermount")
        for cmd in filter(
            None,
            (
                [guestunmount_bin, str(mount_point)] if guestunmount_bin else None,
                [fusermount_bin, "-u", str(mount_point)] if fusermount_bin else None,
            ),
        ):
            try:
                await run_privileged_cmd(cmd, check=False)
            except Exception as exc:
                logger.debug("卸载命令失败 %s: %s", cmd, exc)

        if await _is_mounted(mount_point):
            logger.warning("离线 VFS 卸载后仍显示已挂载: %s", mount_point)
        else:
            logger.info("离线 VFS 已卸载: %s", mount_point)
