# -*- coding: utf-8 -*-
import re
import logging
import posixpath
import shlex
import asyncssh
from datetime import datetime
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 访客机可能是新版 OpenWrt/Dropbear（现代 KEX）或旧版 Dropbear（仅 SHA1 KEX）。
# 旧版 Dropbear 在 known_hosts=None 时还会因算法列表过长导致握手 reset（asyncssh #263）。
_SSH_CONNECT_PROFILES: tuple[dict[str, list[str]], ...] = (
    {
        "kex_algs": [
            "curve25519-sha256",
            "curve25519-sha256@libssh.org",
            "ecdh-sha2-nistp256",
            "diffie-hellman-group16-sha512",
            "diffie-hellman-group14-sha256",
        ],
        "server_host_key_algs": [
            "ssh-ed25519",
            "ecdsa-sha2-nistp256",
            "rsa-sha2-256",
            "rsa-sha2-512",
            "ssh-rsa",
        ],
        "encryption_algs": [
            "chacha20-poly1305@openssh.com",
            "aes128-ctr",
            "aes256-ctr",
            "aes128-gcm@openssh.com",
        ],
        "mac_algs": [
            "umac-64-etm@openssh.com",
            "hmac-sha2-256-etm@openssh.com",
            "hmac-sha2-256",
        ],
    },
    {
        "kex_algs": ["diffie-hellman-group14-sha1", "diffie-hellman-group1-sha1"],
        "server_host_key_algs": ["ssh-rsa"],
        "encryption_algs": ["aes128-cbc", "3des-cbc"],
        "mac_algs": ["hmac-sha1", "hmac-md5"],
    },
    {
        "kex_algs": ["diffie-hellman-group1-sha1"],
        "server_host_key_algs": ["ssh-rsa", "ssh-dss"],
        "encryption_algs": ["3des-cbc", "aes128-cbc"],
        "mac_algs": ["hmac-md5", "hmac-sha1"],
    },
)


class GuestPathNotFoundError(Exception):
    def __init__(self, path: str, message: str):
        self.path = path
        self.message = message
        super().__init__(message)


async def get_ssh_connection(host: str, port: int) -> asyncssh.SSHClientConnection:
    """
    建立与 QEMU 访客机 (OpenWrt) 的 SSH 连接，自动适配新旧 Dropbear/OpenSSH 算法。
    """
    settings = get_settings()
    username = settings.FSEMS_GUEST_SSH_USER or "root"
    # OpenWrt root 默认空密码；不能用 `or None`，否则 asyncssh 不会尝试 password 认证
    password = settings.FSEMS_GUEST_SSH_PASSWORD

    logger.info(f"正在建立 SSH 连接: {username}@{host}:{port}")

    last_error: Exception | None = None
    for index, profile in enumerate(_SSH_CONNECT_PROFILES, start=1):
        try:
            return await asyncssh.connect(
                host,
                port=port,
                username=username,
                password=password,
                known_hosts=None,
                preferred_auth=["password", "keyboard-interactive"],
                **profile,
            )
        except (asyncssh.Error, OSError, ConnectionError, ConnectionResetError) as exc:
            last_error = exc
            logger.warning(
                "SSH 连接失败 (profile %s/%s) %s@%s:%s: %s",
                index,
                len(_SSH_CONNECT_PROFILES),
                username,
                host,
                port,
                exc,
            )

    assert last_error is not None
    raise last_error

# 匹配 ls -la 或 ls -lad 输出的正则表达式
# 包含权限、硬链接数、拥有者、组、大小、日期、时间/年份、文件名/路径
LS_RE = re.compile(
    r'^([bcdlsp-][rwxr-x-]{9})\s+\d+\s+(\S+)\s+(\S+)\s+(\d+)\s+([A-Za-z]{3}\s+\d+\s+[\d:]+|\w{3}\s+\d+\s+\d{4})\s+(.+)$'
)

def parse_ls_line(line: str, parent_path: str) -> dict | None:
    """
    解析 ls 输出的一行，返回包含 name, path, is_dir, size, mtime 的字典
    """
    line = line.strip()
    if not line:
        return None
    match = LS_RE.match(line)
    if not match:
        return None
    
    mode, owner, group, size_str, date_str, full_name_or_path = match.groups()
    is_dir = mode.startswith('d')
    size = int(size_str)
    
    # 剔除软链接的目标路径，只保留链接本身 (例如 "/bin/sh -> busybox" 提取出 "/bin/sh" 或 "sh")
    if mode.startswith('l') and " -> " in full_name_or_path:
        full_name_or_path = full_name_or_path.split(" -> ")[0]

    # 判断返回的是完整路径还是单纯的文件名
    if full_name_or_path.startswith("/"):
        full_path = posixpath.normpath(full_name_or_path)
        name = posixpath.basename(full_path)
    else:
        name = full_name_or_path
        full_path = posixpath.normpath(posixpath.join(parent_path, name))
        
    if not name:
        name = "/"

    # 解析时间戳
    mtime = 0
    now = datetime.now()
    clean_date_str = " ".join(date_str.split())
    # 尝试多种日期格式解析
    for fmt in ("%b %d %H:%M", "%b %d %Y", "%d %b %H:%M", "%d %b %Y"):
        try:
            dt = datetime.strptime(clean_date_str, fmt)
            if "%H:%M" in fmt:
                dt = dt.replace(year=now.year)
                # 如果解析出来的日期在未来大于1天，则认为是去年
                if (dt - now).days > 1:
                    dt = dt.replace(year=now.year - 1)
            mtime = int(dt.timestamp())
            break
        except ValueError:
            continue

    return {
        "name": name,
        "path": full_path,
        "is_dir": is_dir,
        "size": size,
        "mtime": mtime
    }

async def list_guest_directory(host: str, port: int, path: str) -> list[dict]:
    """
    通过 SSH 浏览访客机指定目录，支持 find 和 ls 解析，提供高兼容性
    """
    quoted_path = shlex.quote(path)
    entries = []
    
    async with await get_ssh_connection(host, port) as conn:
        # 首先尝试文档要求的 find {path} -maxdepth 1 -exec ls -lad {} + 
        cmd = f"find {quoted_path} -maxdepth 1 -exec ls -lad {{}} +"
        logger.info(f"执行远程命令: {cmd}")
        result = await conn.run(cmd)
        
        if result.exit_status != 0:
            # 如果 find 命令不支持或报错，回退到标准的 ls -la
            logger.warning(f"find 命令执行失败，回退到 ls -la. 错误: {result.stderr.strip()}")
            fallback_cmd = f"ls -la {quoted_path}"
            result = await conn.run(fallback_cmd)
            if result.exit_status != 0:
                stderr = (result.stderr or "").strip()
                raise GuestPathNotFoundError(
                    path,
                    f"目录不存在或无法读取: {path}" + (f" ({stderr})" if stderr else ""),
                )
        
        lines = result.stdout.splitlines()
        for line in lines:
            parsed = parse_ls_line(line, path)
            if parsed:
                # 排除当前目录自身 (除非是根目录本身)
                norm_queried = posixpath.normpath(path)
                norm_entry = posixpath.normpath(parsed["path"])
                
                # 排除 '.'、'..' 以及当前被查询目录本身
                if parsed["name"] in (".", ".."):
                    continue
                if norm_queried != "/" and norm_queried == norm_entry:
                    continue
                
                entries.append(parsed)
                
    # 按目录优先、字母升序对结果排序
    entries.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return entries


def normalize_guest_path(path: str) -> str:
    normalized = posixpath.normpath(path.strip() or "/")
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    parts = [p for p in normalized.split("/") if p]
    if ".." in parts:
        raise GuestPathNotFoundError(path, "Path outside guest root")
    return normalized if normalized else "/"


async def guest_mkdir(host: str, port: int, path: str) -> None:
    target = normalize_guest_path(path)
    quoted = shlex.quote(target)
    async with await get_ssh_connection(host, port) as conn:
        result = await conn.run(f"mkdir -p {quoted}")
        if result.exit_status != 0:
            raise RuntimeError(result.stderr.strip() or f"mkdir failed: {target}")


async def guest_remove(host: str, port: int, path: str) -> None:
    target = normalize_guest_path(path)
    if target == "/":
        raise RuntimeError("Cannot delete root directory")
    quoted = shlex.quote(target)
    async with await get_ssh_connection(host, port) as conn:
        result = await conn.run(f"rm -rf {quoted}")
        if result.exit_status != 0:
            raise RuntimeError(result.stderr.strip() or f"delete failed: {target}")


async def guest_rename(host: str, port: int, src: str, dest: str) -> None:
    src_path = normalize_guest_path(src)
    dest_path = normalize_guest_path(dest)
    async with await get_ssh_connection(host, port) as conn:
        result = await conn.run(f"mv {shlex.quote(src_path)} {shlex.quote(dest_path)}")
        if result.exit_status != 0:
            raise RuntimeError(result.stderr.strip() or f"rename failed: {src_path}")
