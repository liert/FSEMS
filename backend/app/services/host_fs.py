from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings


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
            stat = entry.stat()
            is_dir = entry.is_dir()
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
                "size": stat.st_size,
                "mtime": int(stat.st_mtime),
            }
        )
    return entries
