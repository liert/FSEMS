# -*- coding: utf-8 -*-
import asyncio
import logging
import subprocess

from app.services.qemu_manager import run_cmd

logger = logging.getLogger(__name__)

async def run_sudo_cmd(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    """
    以 sudo -S 形式执行特权命令，并通过标准输入传入密码 'kali'。
    """
    cmd = ["sudo", "-S"] + args
    logger.info("执行特权命令: %s", " ".join(cmd))
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    # 传入 sudo 密码
    stdout, stderr = await proc.communicate(input=b"kali\n")
    
    result = subprocess.CompletedProcess(
        args=cmd,
        returncode=proc.returncode or 0,
        stdout=stdout.decode(),
        stderr=stderr.decode(),
    )
    
    if check and result.returncode != 0:
        err_clean = result.stderr.replace("[sudo] password for kali: ", "").strip()
        logger.error("特权命令失败: %s. 错误信息: %s", " ".join(cmd), err_clean)
        raise RuntimeError(err_clean or f"Command failed: {' '.join(cmd)}")
        
    return result

async def add_tap_to_bridge(tap: str, bridge: str, user: str) -> None:
    """
    创建指定用户的 TAP 网卡设备并加入网桥 (需要 root 特权)。
    """
    await run_sudo_cmd(["ip", "tuntap", "add", "dev", tap, "mode", "tap", "user", user], check=False)
    await run_sudo_cmd(["ip", "link", "set", tap, "up"], check=False)
    await run_sudo_cmd(["brctl", "addif", bridge, tap], check=False)

async def remove_tap(tap: str, bridge: str) -> None:
    """
    将网卡移出网桥并删除 TAP 设备 (需要 root 特权)。
    """
    await run_sudo_cmd(["brctl", "delif", bridge, tap], check=False)
    await run_sudo_cmd(["ip", "link", "delete", tap], check=False)

async def bridge_exists(bridge: str) -> bool:
    """
    判断指定网桥是否存在 (普通用户可执行)。
    """
    try:
        result = await run_cmd(["ip", "link", "show", bridge], check=False)
        return result.returncode == 0
    except Exception:
        return False
