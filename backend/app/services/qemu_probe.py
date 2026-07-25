# -*- coding: utf-8 -*-
"""探测本机 QEMU 二进制支持的 CPU 型号等能力。"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

# 仅允许以 qemu-system- 开头的可执行文件名，防止任意命令执行
_QEMU_NAME_RE = re.compile(r"^qemu-system-[A-Za-z0-9._+-]+$")
_ALLOWED_BIN_DIRS = (
    Path("/usr/bin"),
    Path("/usr/local/bin"),
    Path("/bin"),
    Path("/usr/libexec"),
)


class QemuProbeError(Exception):
    """探测失败（路径非法、可执行文件不存在、命令失败等）。"""


def resolve_qemu_binary(qemu_binary: str) -> Path:
    """
    将用户填写的 qemu_binary 解析为安全可执行路径。
    允许短名（如 qemu-system-aarch64）或绝对路径；拒绝 shell 元字符与非 qemu-system 程序。
    """
    raw = (qemu_binary or "").strip()
    if not raw:
        raise QemuProbeError("qemu_binary 不能为空")
    if any(ch in raw for ch in ("\n", "\r", "\x00", ";", "|", "&", "$", "`", ">", "<")):
        raise QemuProbeError("qemu_binary 包含非法字符")

    path = Path(raw)
    if path.is_absolute():
        resolved = path.resolve()
        name = resolved.name
        if not _QEMU_NAME_RE.match(name):
            raise QemuProbeError("仅允许 qemu-system-* 可执行文件")
        if not any(resolved.is_relative_to(d) for d in _ALLOWED_BIN_DIRS):
            # is_relative_to 在解析后的绝对路径上检查；兼容软链到允许目录的情况
            real = Path(os.path.realpath(resolved))
            if not any(real.is_relative_to(d.resolve()) for d in _ALLOWED_BIN_DIRS):
                raise QemuProbeError(f"不允许的 QEMU 路径: {resolved}")
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise QemuProbeError(f"QEMU 不可执行或不存在: {resolved}")
        return resolved

    # 短名：通过 PATH 查找
    name = Path(raw).name
    if name != raw or not _QEMU_NAME_RE.match(name):
        raise QemuProbeError("qemu_binary 须为 qemu-system-* 短名或允许目录下的绝对路径")
    found = shutil.which(name)
    if not found:
        raise QemuProbeError(f"未在 PATH 中找到: {name}")
    return Path(found).resolve()


def parse_cpu_help(text: str) -> list[str]:
    """
    解析 `qemu-system-* -cpu help` 输出。
    兼容 aarch64 缩进列表、x86「x86 Name …」、MIPS「MIPS 'Name'」等格式。
    """
    cpus: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # x86 后半段是 CPUID flags 列表，到此结束
        if stripped.startswith("Recognized CPUID") or stripped.startswith("CPUID flags"):
            break
        lower = stripped.lower()
        if lower.startswith("available cpus") or lower.startswith("available cpu"):
            continue

        mips = re.match(r"^MIPS\s+'([^']+)'", stripped)
        if mips:
            cpus.append(mips.group(1))
            continue

        x86 = re.match(r"^(?:x86|X86)\s+(\S+)", stripped)
        if x86:
            cpus.append(x86.group(1))
            continue

        # ARM / 其它：行首空白 + 型号名
        if line[:1] in (" ", "\t"):
            name = stripped.split()[0]
            # 过滤表头/噪音
            if name and name not in ("Available", "CPU", "CPUs:"):
                cpus.append(name)
            continue

        # 少数版本无缩进，整行仅一个 token
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", stripped):
            cpus.append(stripped)

    # 去重并保持大致字母序
    seen: set[str] = set()
    ordered: list[str] = []
    for name in cpus:
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    ordered.sort(key=str.lower)
    return ordered


async def list_cpu_models(qemu_binary: str) -> list[str]:
    """执行 qemu -cpu help 并返回 CPU 型号列表。"""
    binary = resolve_qemu_binary(qemu_binary)
    try:
        proc = await asyncio.create_subprocess_exec(
            str(binary),
            "-cpu",
            "help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise QemuProbeError(f"无法启动 QEMU: {binary}") from exc

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError as exc:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise QemuProbeError("查询 CPU 型号超时") from exc

    text = (stdout or b"").decode(errors="replace")
    # 部分版本 help 非 0 退出仍有有效输出
    models = parse_cpu_help(text)
    if not models:
        logger.warning("解析 CPU 列表为空 binary=%s rc=%s out=%r", binary, proc.returncode, text[:500])
        raise QemuProbeError(
            f"未能从 {binary.name} 解析出 CPU 型号"
            + (f"（exit {proc.returncode}）" if proc.returncode else "")
        )
    return models
