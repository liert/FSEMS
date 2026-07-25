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
            try:
                stat = entry.stat(follow_symlinks=False)
                is_dir = False
            except Exception:
                continue

        entries.append(
            {
                "name": entry.name,
                "path": str(entry),
                "is_dir": is_dir,
                "size": 0 if is_dir else stat.st_size,
                "mtime": int(stat.st_mtime),
            }
        )
    return entries
