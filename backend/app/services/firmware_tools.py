from __future__ import annotations

import gzip
import logging
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import HTTPException, status

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SUPPORTED_FILESYSTEMS = {"ext4", "squashfs", "f2fs"}
_OUTPUT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_COMMAND_TIMEOUT_SEC = 15 * 60


def _bad_request(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error_code": code, "message": message})


def resolve_source_path(raw_path: str) -> Path:
    """Resolve an arbitrary host source path, accepting regular files only."""
    path_text = (raw_path or "").strip()
    if not path_text:
        raise _bad_request("FS_PATH_REQUIRED", "请输入源镜像路径")

    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = get_settings().workspace_path / candidate
    resolved = candidate.resolve()
    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_code": "FS_PATH_NOT_FOUND", "message": f"源镜像不存在或不是普通文件: {path_text}"},
        )
    return resolved


def _run_command(args: list[str], *, timeout: int = _COMMAND_TIMEOUT_SEC) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise RuntimeError(f"系统缺少转换工具: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"转换命令超时: {args[0]}") from exc


def _file_signature(path: Path) -> bytes:
    with path.open("rb") as stream:
        return stream.read(2048)


def detect_filesystem(path: Path) -> str:
    """Detect the filesystem from magic bytes, with file(1) as a fallback."""
    signature = _file_signature(path)
    if signature.startswith(b"hsqs") or signature.startswith(b"sqsh"):
        return "squashfs"
    if len(signature) >= 1082 and signature[1080:1082] == b"\x53\xef":
        return "ext4"
    if len(signature) >= 1028 and signature[1024:1028] == b"\x10\x20\xf5\xf2":
        return "f2fs"

    result = _run_command(["file", "-b", str(path)], timeout=30)
    description = result.stdout.lower()
    if "squashfs" in description:
        return "squashfs"
    if "f2fs" in description:
        return "f2fs"
    if "ext2" in description or "ext3" in description or "ext4" in description:
        return "ext4"
    raise _bad_request("UNSUPPORTED_FILESYSTEM", f"无法识别源镜像文件系统: {result.stdout.strip() or path.name}")


def _materialize_source(source: Path, work_dir: Path) -> Path:
    if source.suffix.lower() != ".gz":
        return source
    decompressed = work_dir / "source.img"
    try:
        with gzip.open(source, "rb") as source_stream, decompressed.open("wb") as dest_stream:
            shutil.copyfileobj(source_stream, dest_stream)
    except OSError as exc:
        raise RuntimeError(f"解压源镜像失败: {exc}") from exc
    return decompressed


def _extract_with_debugfs(source: Path, staging: Path) -> None:
    result = _run_command(["debugfs", "-R", f"rdump / {staging}", str(source)])
    if result.returncode != 0 or not any(staging.iterdir()):
        raise RuntimeError(f"Ext4 提取失败: {(result.stderr or result.stdout).strip()}")


def _extract_with_unsquashfs(source: Path, staging: Path) -> None:
    result = _run_command(["unsquashfs", "-d", str(staging), "-f", str(source)])
    if result.returncode != 0 or not any(staging.iterdir()):
        raise RuntimeError(f"SquashFS 提取失败: {(result.stderr or result.stdout).strip()}")


def _guestfish_copy_out(source: Path, staging: Path) -> None:
    result = _run_command(
        ["guestfish", "--ro", "--format=raw", "-a", str(source), "-m", "/dev/sda", "copy-out", "/", str(staging)]
    )
    if result.returncode != 0 or not any(staging.iterdir()):
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"F2FS 提取失败（需要可用的 libguestfs/guestfish）: {detail}")


def _extract_source(source: Path, source_type: str, staging: Path) -> None:
    if source_type == "ext4":
        _extract_with_debugfs(source, staging)
    elif source_type == "squashfs":
        _extract_with_unsquashfs(source, staging)
    elif source_type == "f2fs":
        _guestfish_copy_out(source, staging)
    else:
        raise RuntimeError(f"不支持的源文件系统: {source_type}")


def _tree_size(path: Path) -> int:
    total = 0
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def _image_size_bytes(staging: Path, requested_mb: int | None) -> int:
    # A rootfs tree can contain many files, extended metadata and sparse files.
    # A small fixed margin is not enough for ext4: mkfs reserves blocks for
    # metadata (and previously reserved 5% for root), which can make
    # ``mkfs.ext4 -d`` fail with ENOSPC even when the apparent file total fits.
    # Leave a proportional margin plus a fixed metadata allowance.  This also
    # gives a useful amount of headroom for a guest to create runtime files.
    tree_size = _tree_size(staging)
    estimated = max(128 * 1024 * 1024, int(tree_size * 1.25) + 64 * 1024 * 1024)
    if requested_mb is not None:
        estimated = max(estimated, requested_mb * 1024 * 1024)
    return ((estimated + 1024 * 1024 - 1) // (1024 * 1024)) * 1024 * 1024


def _populate_f2fs(image: Path, staging: Path) -> None:
    items = sorted(staging.iterdir(), key=lambda item: item.name)
    if not items:
        return
    command = ["guestfish", "--rw", "--format=raw", "-a", str(image), "-m", "/dev/sda", "copy-in"]
    command.extend(str(item) for item in items)
    command.append("/")
    result = _run_command(command)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"F2FS 写入失败（需要可用的 libguestfs/guestfish）: {detail}")


def _create_target(staging: Path, target: Path, target_type: str, size_mb: int | None) -> None:
    if target_type == "squashfs":
        result = _run_command(["mksquashfs", str(staging), str(target), "-noappend", "-all-root", "-comp", "xz"])
        if result.returncode != 0:
            raise RuntimeError(f"SquashFS 创建失败: {(result.stderr or result.stdout).strip()}")
        return

    target_size = _image_size_bytes(staging, size_mb)
    if target_type == "ext4":
        # Rootfs images do not need ext4's default 5% reserved-block pool;
        # disabling it avoids wasting capacity that was just calculated for
        # the files being populated. If the source tree was only partially
        # readable while sizing it, retry with a larger image on ENOSPC.
        for attempt in range(3):
            with target.open("wb") as stream:
                stream.truncate(target_size)
            result = _run_command(
                ["mkfs.ext4", "-q", "-F", "-m", "0", "-d", str(staging), str(target)]
            )
            if result.returncode == 0:
                return
            detail = (result.stderr or result.stdout).strip()
            if attempt == 2 or not any(
                token in detail.lower() for token in ("allocate", "enospc", "no space")
            ):
                raise RuntimeError(f"ext4 创建失败: {detail}")
            target_size *= 2
            logger.warning(
                "RootFS 内容超出初始 ext4 镜像容量，扩大到 %d MiB 后重试",
                target_size // (1024 * 1024),
            )
        return
    elif target_type == "f2fs":
        with target.open("wb") as stream:
            stream.truncate(target_size)
        result = _run_command(["mkfs.f2fs", "-q", "-f", str(target)])
    else:
        raise RuntimeError(f"不支持的目标文件系统: {target_type}")
    if result.returncode != 0:
        raise RuntimeError(f"{target_type} 创建失败: {(result.stderr or result.stdout).strip()}")
    if target_type == "f2fs":
        _populate_f2fs(target, staging)


def create_filesystem_image_from_tree(
    source_dir: Path,
    target: Path,
    target_type: str,
    size_mb: int | None = None,
) -> None:
    """Create a bootable filesystem image from an already extracted rootfs tree."""
    if target_type not in SUPPORTED_FILESYSTEMS:
        raise ValueError(f"不支持的目标文件系统: {target_type}")
    target.parent.mkdir(parents=True, exist_ok=True)
    _create_target(source_dir, target, target_type, size_mb)


def _output_directory() -> Path:
    path = get_settings().workspace_path / "firmware-tools" / "filesystem-converter"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def _output_filename(source: Path, target_type: str, requested: str | None) -> str:
    suffix = ".squashfs" if target_type == "squashfs" else ".img"
    if requested:
        name = requested.strip()
        if not _OUTPUT_NAME_RE.fullmatch(name):
            raise _bad_request("INVALID_OUTPUT_NAME", "输出文件名只能包含字母、数字、点、下划线和短横线")
        if not name.lower().endswith(suffix):
            name += suffix
        return name
    base = source.name
    for ending in (".img.gz", ".squashfs", ".f2fs", ".img", ".raw", ".gz"):
        if base.lower().endswith(ending):
            base = base[: -len(ending)]
            break
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip(".-") or "converted-rootfs"
    return f"{base}-{target_type}{suffix}"


def convert_filesystem(
    source_path: str,
    source_type: str,
    target_type: str,
    output_name: str | None = None,
    size_mb: int | None = None,
) -> dict[str, str | int]:
    if target_type not in SUPPORTED_FILESYSTEMS:
        raise _bad_request("UNSUPPORTED_FILESYSTEM", f"不支持的目标文件系统: {target_type}")
    source = resolve_source_path(source_path)
    output_dir = _output_directory()
    output = output_dir / _output_filename(source, target_type, output_name)
    if output.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_code": "OUTPUT_EXISTS", "message": f"输出文件已存在: {output}"},
        )
    if source == output:
        raise _bad_request("INVALID_OUTPUT_PATH", "输出文件不能覆盖源镜像")

    started = time.monotonic()
    temp_root = Path(tempfile.mkdtemp(prefix=".fs-convert-", dir=output_dir))
    temp_output = temp_root / output.name
    try:
        materialized_source = _materialize_source(source, temp_root)
        detected = detect_filesystem(materialized_source)
        if source_type != "auto" and source_type != detected:
            raise _bad_request(
                "SOURCE_FILESYSTEM_MISMATCH",
                f"源镜像实际为 {detected}，但选择了 {source_type}",
            )
        if detected == target_type:
            raise _bad_request("SAME_FILESYSTEM", "源文件系统与目标文件系统相同，无需转换")

        staging = temp_root / "rootfs"
        staging.mkdir()
        _extract_source(materialized_source, detected, staging)
        _create_target(staging, temp_output, target_type, size_mb)
        temp_output.replace(output)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("文件系统转换失败 source=%s target=%s", source, target_type)
        raise _bad_request("FILESYSTEM_CONVERT_FAILED", str(exc)) from exc
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    return {
        "source_path": str(source),
        "source_type": detected,
        "target_type": target_type,
        "output_path": str(output),
        "output_size_bytes": output.stat().st_size,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
