"""
iot-tools 集成客户端。

子模块路径：third_party/iot-tools（https://github.com/liert/iot-tools）。
优先使用 PATH / IOT_TOOLS_BIN 中的 CLI；后续可改为直接 import 库 API。
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 仓库内默认子模块相对 backend 工作目录
_DEFAULT_SUBMODULE = Path(__file__).resolve().parents[3] / "third_party" / "iot-tools"


def resolve_iot_tools_bin() -> str:
    """解析 iot-tools 可执行入口。"""
    settings = get_settings()
    configured = (getattr(settings, "IOT_TOOLS_BIN", None) or os.environ.get("IOT_TOOLS_BIN") or "").strip()
    if configured:
        return configured
    found = shutil.which("iot-tools")
    if found:
        return found
    # 未安装 editable 时，用 python -m iot_tools（需已 pip install -e）
    return "iot-tools"


def iot_tools_available() -> bool:
    """CLI 是否在 PATH 中可用。"""
    bin_name = resolve_iot_tools_bin()
    if bin_name != "iot-tools" and Path(bin_name).is_file():
        return os.access(bin_name, os.X_OK)
    return shutil.which(bin_name) is not None


def format_remote(user: str, host: str, remote_path: str) -> str:
    """拼成 iot-tools 期望的 user@host:/abs/path。"""
    path = remote_path if remote_path.startswith("/") else f"/{remote_path}"
    return f"{user}@{host}:{path}"


async def smart_scp(
    local_path: str | Path,
    remote: str,
    *,
    cwd: str | Path | None = None,
    dry_run: bool = False,
    timeout_sec: float = 600,
) -> str:
    """
    调用 `iot-tools scp` 将本地文件拷到远端（可解析 ELF NEEDED 依赖）。

    Args:
        local_path: 本地文件路径
        remote: user@host:/absolute/path
        cwd: 依赖搜索根目录（iot-tools 在 cwd 下 find 同名 .so）
        dry_run: 仅打印命令
        timeout_sec: 超时秒数

    Returns:
        合并的 stdout/stderr 文本
    """
    local = str(local_path)
    cmd = [resolve_iot_tools_bin(), "scp"]
    if dry_run:
        cmd.append("--dry-run")
    cmd.extend([local, remote])

    workdir = str(cwd) if cwd else None
    logger.info("iot-tools scp: %s -> %s (cwd=%s)", local, remote, workdir)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workdir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "iot-tools 未安装或不在 PATH。请执行: "
            "pip install -e ../third_party/iot-tools"
        ) from exc

    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"iot-tools scp 超时 ({timeout_sec}s)") from exc

    text = (out_b or b"").decode(errors="replace") + (err_b or b"").decode(errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(text.strip() or f"iot-tools scp 失败 (code={proc.returncode})")
    return text.strip()


async def smart_scp_to_guest(
    local_path: str | Path,
    guest_host: str,
    remote_path: str,
    *,
    cwd: str | Path | None = None,
    user: str | None = None,
    dry_run: bool = False,
    timeout_sec: float = 600,
) -> str:
    """面向 FSEMS 实例访客机的便捷封装。"""
    settings = get_settings()
    ssh_user = user or settings.FSEMS_GUEST_SSH_USER or "root"
    remote = format_remote(ssh_user, guest_host, remote_path)
    return await smart_scp(local_path, remote, cwd=cwd, dry_run=dry_run, timeout_sec=timeout_sec)
