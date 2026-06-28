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
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
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
        raise RuntimeError(
            f"特权命令执行失败: {err_clean or 'Permission Denied'}\n"
            f"👉 请确保后端服务是以 sudo / root 启动的（如: sudo ../backend/.venv/bin/uvicorn app.main:app --reload）"
        )
        
    return result

async def add_tap_to_bridge(tap: str, bridge: str, user: str) -> None:
    """
    创建指定用户的 TAP 网卡设备并加入网桥 (需要 root 特权)。
    """
    await run_privileged_cmd(["ip", "tuntap", "add", "dev", tap, "mode", "tap", "user", user], check=False)
    await run_privileged_cmd(["ip", "link", "set", tap, "up"], check=False)
    await run_privileged_cmd(["brctl", "addif", bridge, tap], check=False)

async def remove_tap(tap: str, bridge: str) -> None:
    """
    将网卡移出网桥并删除 TAP 设备 (需要 root 特权)。
    """
    await run_privileged_cmd(["brctl", "delif", bridge, tap], check=False)
    await run_privileged_cmd(["ip", "link", "delete", tap], check=False)

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
        await run_privileged_cmd(["ip", "link", "add", "name", bridge, "type", "bridge"], check=False)
        await run_privileged_cmd(["ip", "link", "set", bridge, "up"], check=False)
        
    if host_ip:
        # 检查是否已分配该 IP，没有则添加
        try:
            proc = await asyncio.create_subprocess_exec(
                "ip", "addr", "show", "dev", bridge,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            if host_ip not in stdout.decode():
                logger.info(f"为网桥 {bridge} 分配 Host 端口 IP: {host_ip}/24...")
                await run_privileged_cmd(["ip", "addr", "add", f"{host_ip}/24", "dev", bridge], check=False)
        except Exception as e:
            logger.warning(f"检查或分配网桥 {bridge} 的 IP 失败: {e}")
