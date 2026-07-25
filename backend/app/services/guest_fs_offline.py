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
# debugfs -R "ls -l" 示例：
#   12   40755 (2)      0      0    4096 14-May-2026 06:42 bin
# mode 字段为八进制（40755），不能按十进制 int()。
_DEBUGFS_LS = re.compile(
    r"^\s*\d+\s+([0-7]+)\s+\(\d+\)\s+\d+\s+\d+\s+(\d+)\s+"
    r"(?:(\d{1,2}-\w{3}-\d{4})\s+(\d{1,2}:\d{2})\s+)?"
    r"(.+)$"
)
_S_IFMT = 0o170000
_S_IFDIR = 0o040000
_S_IFLNK = 0o120000


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
    """
    将访客机 POSIX 路径映射到挂载点下的宿主机路径。
    对路径上的符号链接按段解析，支持链接到目录（OpenWrt /lib -> usr/lib）。
    """
    mount_resolved = mount_root.resolve()
    normalized = posixpath.normpath(guest_path.strip() or "/")
    if normalized == "/":
        target = mount_resolved
    else:
        # 逐段拼接并跟随符号链接（相对链接按当前目录解析）
        target = mount_resolved
        for part in normalized.strip("/").split("/"):
            if not part or part == ".":
                continue
            if part == "..":
                if target == mount_resolved:
                    raise GuestPathNotFoundError(guest_path, "Path outside guest root")
                target = target.parent
                continue
            nxt = target / part
            try:
                if nxt.is_symlink():
                    # Path.is_dir() 会跟随链接；先检查链接本身
                    if nxt.is_dir():
                        target = nxt.resolve()
                    else:
                        target = nxt
                else:
                    target = nxt
            except OSError:
                target = nxt

    try:
        # 允许 resolve 后仍在 mount 树内（跟随链接后的真实路径）
        real = target.resolve(strict=False)
        real.relative_to(mount_resolved)
        target = real
    except ValueError as exc:
        raise GuestPathNotFoundError(
            guest_path,
            "Path outside guest root",
        ) from exc
    except OSError:
        pass

    if not target.exists():
        raise GuestPathNotFoundError(guest_path, f"目录不存在或无法读取: {guest_path}")

    return target


def list_offline_guest_directory(mount_root: Path, guest_path: str) -> list[dict]:
    target = resolve_offline_guest_path(mount_root, guest_path)
    # is_dir() 跟随符号链接，链接到目录时可进入
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


def _parse_debugfs_mtime(date_s: str | None, time_s: str | None) -> int:
    """将 debugfs 日期时间转为 unix 秒；解析失败返回 0。"""
    if not date_s or not time_s:
        return 0
    from datetime import datetime

    for fmt in ("%d-%b-%Y %H:%M", "%d-%B-%Y %H:%M"):
        try:
            return int(datetime.strptime(f"{date_s} {time_s}", fmt).timestamp())
        except ValueError:
            continue
    return 0


def _parse_debugfs_ls_line(line: str) -> tuple[str, bool, int, int, bool, str | None] | None:
    """
    解析 debugfs ls -l 一行。
    返回 (name, is_dir, size, mtime_unix, is_link, link_target)。
    is_dir 仅表示真实目录；指向目录的符号链接在后续 _enrich_symlink_dirs 中处理。
    """
    match = _DEBUGFS_LS.match(line.strip())
    if not match:
        return None
    mode = int(match.group(1), 8)
    size = int(match.group(2))
    mtime = _parse_debugfs_mtime(match.group(3), match.group(4))
    name = match.group(5).strip()
    if name in (".", ".."):
        return None
    link_target: str | None = None
    if " -> " in name:
        name, link_target = name.split(" -> ", 1)
        name = name.strip()
        link_target = link_target.strip()
    file_type = mode & _S_IFMT
    is_link = file_type == _S_IFLNK
    is_dir = file_type == _S_IFDIR
    return name, is_dir, size, mtime, is_link, link_target


def _debugfs_ls_raw(drive_path: Path, guest_path: str) -> list[dict]:
    """对 debugfs 路径做一次 ls -l，返回含 is_link/link_target 的条目。"""
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
        name, is_dir, size, mtime, is_link, link_target = parsed
        if parent_guest == "/":
            entry_path = f"/{name}"
        else:
            entry_path = posixpath.join(parent_guest, name)
        entries.append(
            {
                "name": name,
                "path": entry_path,
                "is_dir": is_dir,
                "size": 0 if is_dir else size,
                "mtime": mtime,
                "is_link": is_link,
                "link_target": link_target,
            }
        )
    return entries


def _resolve_link_target(parent: str, link_target: str) -> str:
    if link_target.startswith("/"):
        return posixpath.normpath(link_target)
    return posixpath.normpath(posixpath.join(parent, link_target))


def _debugfs_path_is_dir(drive_path: Path, guest_path: str, *, depth: int = 0) -> bool:
    """判断镜像内路径是否为目录（跟随符号链接，有限深度）。"""
    if depth > 12:
        return False
    normalized = posixpath.normpath(guest_path.strip() or "/")
    if normalized == "/":
        return True
    parent = posixpath.dirname(normalized) or "/"
    name = posixpath.basename(normalized)
    try:
        entries = _debugfs_ls_raw(drive_path, parent)
    except (GuestPathNotFoundError, RuntimeError):
        return False
    for e in entries:
        if e["name"] != name:
            continue
        if e["is_dir"]:
            return True
        if e.get("is_link") and e.get("link_target"):
            target = _resolve_link_target(parent, e["link_target"])
            return _debugfs_path_is_dir(drive_path, target, depth=depth + 1)
        return False
    return False


def _enrich_debugfs_symlink_dirs(drive_path: Path, parent_guest: str, entries: list[dict]) -> None:
    """将指向目录的符号链接标为 is_dir（OpenWrt: lib -> usr/lib）。"""
    for e in entries:
        if e.get("is_dir") or not e.get("is_link") or not e.get("link_target"):
            continue
        target = _resolve_link_target(parent_guest, e["link_target"])
        if _debugfs_path_is_dir(drive_path, target):
            e["is_dir"] = True
            e["size"] = 0


def _resolve_debugfs_guest_path(drive_path: Path, guest_path: str, *, depth: int = 0) -> str:
    """
    将访客路径中的符号链接展开为 debugfs 可 ls 的真实目录路径。
    例如 /lib -> /usr/lib。
    """
    normalized = posixpath.normpath(guest_path.strip() or "/")
    if normalized == "/" or depth > 12:
        return normalized

    parts = [p for p in normalized.split("/") if p]
    cur = "/"
    for i, part in enumerate(parts):
        parent = cur
        try:
            entries = _debugfs_ls_raw(drive_path, parent)
        except (GuestPathNotFoundError, RuntimeError):
            return normalized
        ent = next((e for e in entries if e["name"] == part), None)
        if ent is None:
            return normalized
        if ent.get("is_link") and ent.get("link_target"):
            target = _resolve_link_target(parent, ent["link_target"])
            # 链接目标 + 剩余路径段
            rest = parts[i + 1 :]
            joined = target if not rest else posixpath.join(target, *rest)
            return _resolve_debugfs_guest_path(drive_path, joined, depth=depth + 1)
        cur = posixpath.join(parent, part) if parent != "/" else f"/{part}"
    return cur


def _list_debugfs_guest_directory_sync(drive_path: Path, guest_path: str) -> list[dict]:
    """debugfs 列举；自动跟随路径上的符号链接目录。"""
    normalized = posixpath.normpath(guest_path.strip() or "/")
    resolved = _resolve_debugfs_guest_path(drive_path, normalized)
    entries = _debugfs_ls_raw(drive_path, resolved)
    _enrich_debugfs_symlink_dirs(drive_path, resolved, entries)

    # 对外 path 使用用户请求的逻辑路径前缀，进入子目录时仍用 resolve 保证可列
    # 条目 path 挂在用户当前 guest_path 下，便于面包屑
    parent_guest = normalized
    out: list[dict] = []
    for e in entries:
        name = e["name"]
        if parent_guest == "/":
            entry_path = f"/{name}"
        else:
            entry_path = posixpath.join(parent_guest, name)
        out.append(
            {
                "name": name,
                "path": entry_path,
                "is_dir": e["is_dir"],
                "size": e["size"],
                "mtime": e["mtime"],
            }
        )
    return out


async def list_guest_offline_directory(
    instance_id: str,
    drive_path: Path,
    guest_path: str,
) -> list[dict]:
    """
    离线列举访客机目录：始终读取虚拟机启动磁盘 rootfs.img。

    顺序：debugfs（raw ext4）→ guestmount。
    不会使用自定义 RootFS 解压目录（workspace/.../rootfs），该目录仅作辅助数据，
    与 QEMU 启动盘无关。
    """
    drive_path = drive_path.resolve()
    if not drive_path.is_file():
        raise FileNotFoundError(f"Drive image not found: {drive_path}")

    errors: list[str] = []

    if _tool_path("debugfs"):
        try:
            logger.info("离线 VFS 使用启动盘 debugfs: %s path=%s", drive_path, guest_path)
            return await asyncio.to_thread(_list_debugfs_guest_directory_sync, drive_path, guest_path)
        except GuestPathNotFoundError:
            raise
        except Exception as exc:
            errors.append(f"debugfs: {exc}")
            logger.warning("debugfs 离线浏览失败: %s", exc)

    if _tool_path("guestmount"):
        try:
            logger.info("离线 VFS 使用启动盘 guestmount: %s path=%s", drive_path, guest_path)
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
