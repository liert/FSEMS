"""
iot-tools 集成客户端（子项目 third_party/iot-tools）。

- CLI：`iot-tools scp ...` 或 `python -m iot_tools scp ...`
- FSEMS 双栏：子进程调用；优先「venv 内脚本」或「当前解释器 -m iot_tools」
- 注意：venv 的 python 常是指向 /usr/bin/python3 的符号链接，
  找 sibling 脚本时不要 Path.resolve() 整个 executable。
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import shutil
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int], Awaitable[None] | None]


def _venv_scripts_dir() -> Path:
    """当前解释器所在目录（venv/bin）。不要 resolve()，否则会落到 /usr/bin。"""
    return Path(sys.executable).parent


def resolve_iot_tools_cmd() -> list[str]:
    """
    解析启动 iot-tools 的 argv。

    优先级：
    1. IOT_TOOLS_BIN 为绝对路径或非默认命令名
    2. IOT_TOOLS_BIN 为 -m / module → python -m iot_tools
    3. 与 sys.executable 同目录的 iot-tools 脚本（venv/bin，不 resolve）
    4. PATH 中的 iot-tools
    5. [sys.executable, '-m', 'iot_tools']
    """
    settings = get_settings()
    configured = (getattr(settings, "IOT_TOOLS_BIN", None) or os.environ.get("IOT_TOOLS_BIN") or "").strip()

    if configured in {"-m", "module", "python -m"}:
        return [sys.executable, "-m", "iot_tools"]

    # 显式绝对路径 / 自定义命令（非默认占位 "iot-tools"）
    if configured and configured != "iot-tools":
        return [configured]
    if configured == "iot-tools":
        # 若用户配置了绝对路径式安装且 PATH 可用，下面 which 会命中；
        # 先继续走 venv sibling 逻辑。
        pass

    sibling = _venv_scripts_dir() / "iot-tools"
    if sibling.is_file() and os.access(sibling, os.X_OK):
        return [str(sibling)]

    found = shutil.which("iot-tools")
    if found:
        return [found]

    return [sys.executable, "-m", "iot_tools"]


def resolve_iot_tools_bin() -> str:
    """兼容旧接口。"""
    cmd = resolve_iot_tools_cmd()
    if len(cmd) >= 3 and cmd[1] == "-m":
        return f"{cmd[0]} -m iot_tools"
    return cmd[0]


def iot_tools_available() -> bool:
    """当前解释器能否 import iot_tools（与 uvicorn/Celery 同一 venv 即可）。"""
    try:
        import iot_tools  # noqa: F401

        return True
    except ImportError:
        return False


def format_remote(user: str, host: str, remote_path: str) -> str:
    path = remote_path if remote_path.startswith("/") else f"/{remote_path}"
    return f"{user}@{host}:{path}"


def build_iot_env(
    *,
    port: int | str | None = None,
    password: str | None = None,
    inherit: bool = True,
) -> dict[str, str]:
    """构造 iot-tools 子进程环境（端口 / 密码 / PATH）。"""
    settings = get_settings()
    env = dict(os.environ) if inherit else {}

    venv_bin = str(_venv_scripts_dir())
    path = env.get("PATH", "")
    parts = path.split(os.pathsep) if path else []
    if venv_bin not in parts:
        env["PATH"] = venv_bin + (os.pathsep + path if path else "")

    env["IOT_TOOLS_SSH_PORT"] = str(port if port is not None else 22)

    if password is None:
        password = settings.FSEMS_GUEST_SSH_PASSWORD
    env["IOT_TOOLS_SSH_PASSWORD"] = password if password is not None else ""
    env["IOT_TOOLS_SSH_USER"] = settings.FSEMS_GUEST_SSH_USER or "root"

    return env


async def _run_iot_tools(
    args: list[str],
    *,
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    timeout_sec: float = 600,
    on_line: Callable[[str], None] | None = None,
) -> str:
    cmd = [*resolve_iot_tools_cmd(), *args]
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
            "无法启动 iot-tools。请用与 Celery 相同的解释器安装:\n"
            f"  {sys.executable} -m pip install -e "
            f"{Path(__file__).resolve().parents[3] / 'third_party' / 'iot-tools'}"
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
