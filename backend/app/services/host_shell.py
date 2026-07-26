"""
宿主机交互式 shell（PTY），默认工作目录为文件系统根「/」。

通过 WebSocket 与前端 xterm 双向传输二进制数据；resize 走 JSON 文本帧。
"""

from __future__ import annotations

import asyncio
import errno
import fcntl
import json
import logging
import os
import pty
import signal
import struct
import termios
from pathlib import Path

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    rows = max(1, min(int(rows), 500))
    cols = max(1, min(int(cols), 500))
    packed = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


def _pick_shell() -> str:
    for candidate in (
        os.environ.get("SHELL"),
        "/bin/bash",
        "/bin/zsh",
        "/bin/sh",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return "/bin/sh"


async def run_host_shell_session(
    websocket: WebSocket,
    *,
    cwd: str = "/",
    cols: int = 80,
    rows: int = 24,
) -> None:
    """
    在已 accept 的 WebSocket 上运行宿主 shell 会话，直到断开。
    """
    workdir = cwd if Path(cwd).is_dir() else "/"
    shell = _pick_shell()
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    if "HOME" not in env or not env["HOME"]:
        env["HOME"] = str(Path.home()) if Path.home().is_dir() else "/"

    master_fd, slave_fd = pty.openpty()
    try:
        _set_winsize(master_fd, rows, cols)
    except OSError as exc:
        logger.debug("initial winsize failed: %s", exc)

    try:
        pid = os.fork()
    except OSError:
        os.close(master_fd)
        os.close(slave_fd)
        raise

    if pid == 0:
        # 子进程：绑定 PTY 并 exec shell
        try:
            os.setsid()
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        except OSError:
            pass
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            os.chdir(workdir)
        except OSError:
            try:
                os.chdir("/")
            except OSError:
                pass
        try:
            os.execve(shell, [shell, "-i"], env)
        except OSError:
            os._exit(127)

    # 父进程
    os.close(slave_fd)
    logger.info("host shell started pid=%s cwd=%s shell=%s", pid, workdir, shell)

    async def pump_pty_to_ws() -> None:
        try:
            while True:
                try:
                    data = await asyncio.to_thread(os.read, master_fd, 8192)
                except OSError as exc:
                    if exc.errno in (errno.EIO, errno.EBADF):
                        break
                    logger.debug("pty read error: %s", exc)
                    break
                if not data:
                    break
                try:
                    await websocket.send_bytes(data)
                except Exception:
                    break
        finally:
            pass

    reader = asyncio.create_task(pump_pty_to_ws())

    try:
        while True:
            try:
                message = await websocket.receive()
            except WebSocketDisconnect:
                break
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"] is not None:
                data = message["bytes"]
                if data:
                    try:
                        await asyncio.to_thread(os.write, master_fd, data)
                    except OSError:
                        break
            elif "text" in message and message["text"] is not None:
                text = message["text"]
                if text == "ping":
                    try:
                        await websocket.send_text("pong")
                    except Exception:
                        break
                    continue
                if text.startswith("{") and text.endswith("}"):
                    try:
                        payload = json.loads(text)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        continue
                    if payload.get("type") == "resize":
                        try:
                            _set_winsize(
                                master_fd,
                                int(payload.get("rows", 24)),
                                int(payload.get("cols", 80)),
                            )
                        except (OSError, TypeError, ValueError) as exc:
                            logger.debug("resize failed: %s", exc)
                        continue
                # 纯文本当作输入
                try:
                    await asyncio.to_thread(
                        os.write, master_fd, text.encode("utf-8", errors="replace")
                    )
                except OSError:
                    break

            # 子进程已退出？
            try:
                wpid, _ = os.waitpid(pid, os.WNOHANG)
                if wpid == pid:
                    break
            except ChildProcessError:
                break
    finally:
        reader.cancel()
        try:
            await reader
        except asyncio.CancelledError:
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            os.kill(pid, signal.SIGHUP)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        try:
            # 短暂等待回收
            for _ in range(20):
                try:
                    wpid, _ = os.waitpid(pid, os.WNOHANG)
                    if wpid == pid:
                        break
                except ChildProcessError:
                    break
                await asyncio.sleep(0.05)
            else:
                try:
                    os.kill(pid, signal.SIGKILL)
                    os.waitpid(pid, 0)
                except (ProcessLookupError, ChildProcessError, OSError):
                    pass
        except Exception as exc:
            logger.debug("host shell cleanup: %s", exc)
        logger.info("host shell session ended pid=%s", pid)
