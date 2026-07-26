# -*- coding: utf-8 -*-
import asyncio
import logging
import subprocess

logger = logging.getLogger(__name__)

async def run_privileged_cmd(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """
    执行特权系统命令（例如网桥与网卡创建）。
    若当前用户是 root 则直接执行；否则加上 sudo -n（非交互模式）执行。
    """
    import os
    is_root = os.getuid() == 0 if hasattr(os, "getuid") else False
    
    cmd = args
    if not is_root:
        cmd = ["sudo", "-n"] + args
        
    logger.info("执行特权命令: %s", " ".join(cmd))
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        missing = cmd[1] if not is_root and cmd and cmd[0] == "sudo" else (cmd[0] if cmd else "unknown")
        raise RuntimeError(f"命令不存在: {missing} ({exc})") from exc
    stdout, stderr = await proc.communicate()
    
    result = subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode or 0,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
    )
    
    if check and result.returncode != 0:
        err_clean = result.stderr.strip()
        logger.error("特权命令失败: %s. 错误信息: %s", " ".join(cmd), err_clean)
        raise RuntimeError(err_clean or f"特权命令执行失败 (exit {result.returncode})")
        
    return result

async def _link_exists(name: str) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            "ip", "link", "show", name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False

async def add_tap_to_bridge(tap: str, bridge: str, user: str) -> None:
    """创建 TAP、加入网桥并验证；任一步失败都清理部分资源并抛错。"""
    if await _link_exists(tap):
        await run_privileged_cmd(["ip", "link", "delete", tap], check=True)
    try:
        await run_privileged_cmd(
            ["ip", "tuntap", "add", "dev", tap, "mode", "tap", "user", user],
            check=True,
        )
        await run_privileged_cmd(["ip", "link", "set", "dev", tap, "master", bridge], check=True)
        await run_privileged_cmd(["ip", "link", "set", "dev", tap, "up"], check=True)
    except Exception:
        if await _link_exists(tap):
            await run_privileged_cmd(["ip", "link", "delete", tap], check=False)
        raise

    if not await _link_exists(tap):
        raise RuntimeError(f"TAP 创建后不可见: {tap}")

async def remove_tap(tap: str, bridge: str) -> None:
    """删除 TAP；不存在时保持幂等。"""
    if not await _link_exists(tap):
        return
    await run_privileged_cmd(["ip", "link", "set", "dev", tap, "nomaster"], check=False)
    await run_privileged_cmd(["ip", "link", "delete", tap], check=True)

async def bridge_exists(bridge: str) -> bool:
    """
    判断指定网桥是否存在 (普通用户可执行)。
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "ip", "link", "show", bridge,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
        return proc.returncode == 0
    except Exception:
        return False

async def ensure_bridge_setup(bridge: str, host_ip: str | None = None) -> None:
    """
    检查指定网桥是否存在，若不存在则以特权创建并启用，分配 Host 端的 IP 以打通 SSH 路由。
    """
    if not await bridge_exists(bridge):
        logger.info(f"网桥 {bridge} 不存在，正在以特权自动创建...")
        await run_privileged_cmd(["ip", "link", "add", "name", bridge, "type", "bridge"], check=True)
    await run_privileged_cmd(["ip", "link", "set", "dev", bridge, "up"], check=True)

    if not await bridge_exists(bridge):
        raise RuntimeError(f"网桥创建后不可见: {bridge}")

    if host_ip:
        # 检查是否已分配该 IP，没有则添加
        proc = await asyncio.create_subprocess_exec(
            "ip", "addr", "show", "dev", bridge,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(stderr.decode().strip() or f"无法读取网桥地址: {bridge}")
        if host_ip not in stdout.decode():
            logger.info(f"为网桥 {bridge} 分配 Host 端口 IP: {host_ip}/24...")
            await run_privileged_cmd(
                ["ip", "addr", "add", f"{host_ip}/24", "dev", bridge],
                check=True,
            )
