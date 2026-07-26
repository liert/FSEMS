import os
import shutil
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings


def resolve_instance_host_root(instance_id: str) -> Path:
    """实例宿主机浏览根：优先 rootfs 目录，否则实例工作目录。"""
    settings = get_settings()
    inst_dir = (settings.workspace_path / instance_id).resolve()
    if not inst_dir.is_dir():
        return settings.workspace_path.resolve()

    rootfs_dir = inst_dir / "rootfs"
    if rootfs_dir.is_dir():
        return rootfs_dir.resolve()
    return inst_dir


def resolve_host_directory(path: str, instance_id: str | None = None) -> Path:
    """Resolve a host directory for listing or upload targets."""
    path_str = path.strip()
    if not path_str:
        if instance_id:
            target = resolve_instance_host_root(instance_id)
        else:
            settings = get_settings()
            workspace = settings.workspace_path
            workspace.mkdir(parents=True, exist_ok=True)
            target = workspace.resolve()
    else:
        target = resolve_workspace_path(path_str)

    if not target.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Target is not a directory"},
        )
    return target


def resolve_workspace_path(relative: str) -> Path:
    settings = get_settings()
    workspace = settings.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)

    path_str = relative.strip()
    if not path_str:
        target = workspace.resolve()
    elif path_str.startswith("/"):
        target = Path(path_str).resolve()
    else:
        target = (workspace / path_str).resolve()

    if not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Path not found"},
        )

    workspace_resolved = workspace.resolve()
    try:
        target.relative_to(workspace_resolved)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Path outside workspace"},
        ) from exc

    return target


def _bad_request(message: str, code: str = "FS_INVALID_OP") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error_code": code, "message": message},
    )


def resolve_host_target(path: str, *, must_exist: bool = True) -> Path:
    """解析宿主机操作目标并校验安全性。

    与 resolve_workspace_path 的区别：允许目标尚不存在（mkdir 与 rename 的目的地），
    但同样强制落在 workspace 内，并拒绝直接操作 workspace 根与实例工作目录本身
    （实例目录应通过实例删除流程管理，误删会让实例记录与磁盘失配）。
    """
    settings = get_settings()
    workspace = settings.workspace_path
    workspace.mkdir(parents=True, exist_ok=True)
    workspace_resolved = workspace.resolve()

    path_str = (path or "").strip()
    if not path_str:
        raise _bad_request("Path is required")

    candidate = Path(path_str) if path_str.startswith("/") else workspace / path_str
    name = candidate.name
    if name in ("", ".", ".."):
        raise _bad_request("Invalid path")

    # 只解析父目录：既能挡住经由符号链接目录的逃逸，又允许操作指向 workspace
    # 外部的符号链接条目本身（解压出来的 rootfs 里这类绝对链接非常多）。
    target = candidate.parent.resolve() / name

    try:
        relative = target.relative_to(workspace_resolved)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Path outside workspace"},
        ) from exc

    depth = len(relative.parts)
    if depth == 0:
        raise _bad_request("Refusing to operate on the workspace root", "FS_PROTECTED_PATH")
    if depth == 1:
        raise _bad_request(
            "Refusing to operate on an instance workspace directory",
            "FS_PROTECTED_PATH",
        )

    # is_symlink 兜住断链：断掉的符号链接 exists() 为假，但应当允许删除
    if must_exist and not target.exists() and not target.is_symlink():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": "Path not found"},
        )
    return target


def host_mkdir(path: str) -> Path:
    target = resolve_host_target(path, must_exist=False)
    if target.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "FS_ALREADY_EXISTS", "message": "Target already exists"},
        )
    try:
        target.mkdir(parents=True)
    except OSError as exc:
        raise _bad_request(f"Failed to create directory: {exc}") from exc
    return target


def host_remove(path: str) -> Path:
    target = resolve_host_target(path)
    try:
        # 符号链接按链接本身删除，不跟随到目标目录
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise _bad_request(f"Failed to delete: {exc}") from exc
    return target


def host_rename(path: str, dest_path: str) -> Path:
    src = resolve_host_target(path)
    dest = resolve_host_target(dest_path, must_exist=False)
    if dest == src:
        return src
    if dest.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "FS_ALREADY_EXISTS", "message": "Target already exists"},
        )
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        src.rename(dest)
    except OSError as exc:
        raise _bad_request(f"Failed to rename: {exc}") from exc
    return dest


def list_directory(path: Path) -> list[dict]:
    entries = []
    try:
        items = list(path.iterdir())
    except OSError:
        return []

    def is_dir_safe(p: Path) -> bool:
        try:
            return p.is_dir()
        except Exception:
            return False

    for entry in sorted(items, key=lambda p: (not is_dir_safe(p), p.name.lower())):
        try:
            # is_dir() / stat() 默认跟随符号链接：链接到目录时按目录展示并可进入
            is_dir = entry.is_dir()
            stat = entry.stat()
        except (FileNotFoundError, OSError):
            # 悬空链接：按链接自身取信息，仍然展示出来
            try:
                stat = entry.stat(follow_symlinks=False)
                is_dir = False
            except Exception:
                continue

        is_link = False
        link_target: str | None = None
        try:
            if entry.is_symlink():
                is_link = True
                link_target = os.readlink(entry)
        except OSError:
            pass

        entries.append(
            {
                "name": entry.name,
                "path": str(entry),
                "is_dir": is_dir,
                "size": 0 if is_dir else stat.st_size,
                "mtime": int(stat.st_mtime),
                "is_link": is_link,
                "link_target": link_target,
            }
        )
    return entries
