"""
iot-tools 集成客户端（子项目 third_party/iot-tools）。

- 可独立 CLI：`iot-tools scp ...`
- FSEMS 双栏传输：通过本模块调用同一套指令逻辑
- 认证/端口通过环境变量注入，与 FSEMS 访客机配置一致
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int], Awaitable[None] | None]


def resolve_iot_tools_bin() -> str:
    settings = get_settings()
    configured = (getattr(settings, "IOT_TOOLS_BIN", None) or os.environ.get("IOT_TOOLS_BIN") or "").strip()
    if configured:
        return configured
    found = shutil.which("iot-tools")
    if found:
        return found
    return "iot-tools"


def iot_tools_available() -> bool:
    bin_name = resolve_iot_tools_bin()
    if Path(bin_name).is_file():
        return os.access(bin_name, os.X_OK)
    return shutil.which(bin_name) is not None


def format_remote(user: str, host: str, remote_path: str) -> str:
    path = remote_path if remote_path.startswith("/") else f"/{remote_path}"
    return f"{user}@{host}:{path}"


def build_iot_env(
    *,
    port: int | str | None = None,
    password: str | None = None,
    inherit: bool = True,
) -> dict[str, str]:
    """构造 iot-tools 子进程环境（端口 / 密码）。"""
    settings = get_settings()
    env = dict(os.environ) if inherit else {}

    ssh_port = str(port if port is not None else 22)
    env["IOT_TOOLS_SSH_PORT"] = ssh_port

    # None → 使用 FSEMS 配置；始终写入，便于 OpenWrt 空密码 + sshpass
    if password is None:
        password = settings.FSEMS_GUEST_SSH_PASSWORD
    env["IOT_TOOLS_SSH_PASSWORD"] = password if password is not None else ""

    return env


async def _run_iot_tools(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout_sec: float = 600,
    on_line: Callable[[str], None] | None = None,
) -> str:
    cmd = [resolve_iot_tools_bin(), *args]
    workdir = str(cwd) if cwd else None
    logger.info("iot-tools: %s (cwd=%s)", " ".join(cmd), workdir)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workdir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "iot-tools 未安装。请在 backend venv 中执行: "
            "pip install -e ../third_party/iot-tools"
        ) from exc

    chunks: list[str] = []

    async def _read_stdout() -> None:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="replace")
            chunks.append(text)
            stripped = text.rstrip()
            if stripped:
                logger.info("iot-tools | %s", stripped)
                if on_line:
                    on_line(stripped)

    try:
        await asyncio.wait_for(_read_stdout(), timeout=timeout_sec)
        code = await asyncio.wait_for(proc.wait(), timeout=5)
    except asyncio.TimeoutError as exc:
        proc.kill()
        with contextlib.suppress(ProcessLookupError):
            await proc.wait()
        raise TimeoutError(f"iot-tools 超时 ({timeout_sec}s)") from exc

    output = "".join(chunks).strip()
    if code != 0:
        raise RuntimeError(output or f"iot-tools 失败 (exit={code})")
    return output


async def scp_host_to_guest(
    local_path: str | Path,
    guest_host: str,
    remote_path: str,
    *,
    port: int = 22,
    user: str | None = None,
    password: str | None = None,
    search_root: str | Path | None = None,
    dry_run: bool = False,
    timeout_sec: float = 600,
    progress: ProgressCallback | None = None,
) -> str:
    """
    宿主机 → 访客机。ELF 时在 search_root（默认源文件父目录）解析 NEEDED 依赖。
    """
    settings = get_settings()
    ssh_user = user or settings.FSEMS_GUEST_SSH_USER or "root"
    remote = format_remote(ssh_user, guest_host, remote_path)
    local = Path(local_path)

    root = Path(search_root) if search_root else local.parent
    args = ["scp"]
    if dry_run:
        args.append("--dry-run")
    args.extend(["--search-root", str(root), str(local), remote])

    if progress:
        await _maybe_await(progress(15))

    env = build_iot_env(port=port, password=password)
    # cwd 与 search-root 对齐，避免相对路径歧义
    out = await _run_iot_tools(args, cwd=str(root), env=env, timeout_sec=timeout_sec)

    if progress:
        await _maybe_await(progress(95))
    return out


async def scp_guest_to_host(
    guest_host: str,
    remote_path: str,
    local_dest: str | Path,
    *,
    port: int = 22,
    user: str | None = None,
    password: str | None = None,
    dry_run: bool = False,
    timeout_sec: float = 600,
    progress: ProgressCallback | None = None,
) -> str:
    """访客机 → 宿主机（--pull，不解析依赖）。"""
    settings = get_settings()
    ssh_user = user or settings.FSEMS_GUEST_SSH_USER or "root"
    remote = format_remote(ssh_user, guest_host, remote_path)
    local = Path(local_dest)

    args = ["scp", "--pull"]
    if dry_run:
        args.append("--dry-run")
    args.extend([str(local), remote])

    if progress:
        await _maybe_await(progress(20))

    env = build_iot_env(port=port, password=password)
    workdir = str(local if local.is_dir() else local.parent)
    out = await _run_iot_tools(args, cwd=workdir, env=env, timeout_sec=timeout_sec)

    if progress:
        await _maybe_await(progress(95))
    return out


async def _maybe_await(result: Awaitable[None] | None) -> None:
    if result is not None and asyncio.iscoroutine(result):
        await result


# 兼容旧名称
async def smart_scp(
    local_path: str | Path,
    remote: str,
    *,
    cwd: str | Path | None = None,
    dry_run: bool = False,
    timeout_sec: float = 600,
    port: int = 22,
    password: str | None = None,
) -> str:
    args = ["scp"]
    if dry_run:
        args.append("--dry-run")
    if cwd:
        args.extend(["--search-root", str(cwd)])
    args.extend([str(local_path), remote])
    env = build_iot_env(port=port, password=password)
    return await _run_iot_tools(args, cwd=str(cwd) if cwd else None, env=env, timeout_sec=timeout_sec)


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
    return await scp_host_to_guest(
        local_path,
        guest_host,
        remote_path,
        user=user,
        search_root=cwd,
        dry_run=dry_run,
        timeout_sec=timeout_sec,
    )
