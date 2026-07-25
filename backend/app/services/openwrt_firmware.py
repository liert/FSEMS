# -*- coding: utf-8 -*-
"""从 downloads.openwrt.org 列举版本/内核，并下载到本地 data/kernels。"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# 架构 → OpenWrt targets 路径（QEMU 常用）
ARCH_OPENWRT_TARGET: dict[str, str] = {
    "aarch64": "armsr/armv8",
    "arm64": "armsr/armv8",
    "arm": "armsr/armv7",
    "mips": "malta/be",
    "mipsel": "malta/le",
    "x86_64": "x86/64",
    "amd64": "x86/64",
    "x86": "x86/64",
    "i386": "x86/generic",
}

_HREF_RE = re.compile(r'href="([^"]+)"', re.I)
_VERSION_DIR_RE = re.compile(r"^\d+\.\d+(\.\d+)?(-rc\d+)?/?$")
_SKIP_NAME_RE = re.compile(
    r"(kernel-debug|imagebuilder|sdk|toolchain|llvm-bpf|\.sha256|\.sig|\.asc|"
    r"packages/|config\.buildinfo|feeds\.buildinfo|version\.buildinfo|profiles\.json)",
    re.I,
)
_KERNEL_NAME_RE = re.compile(
    r"(kernel\.bin|vmlinux(\.elf|\.bin)?|vmlinuz)(\.(gz|xz|zst))?$",
    re.I,
)

# 简单内存缓存，避免频繁打官方站
_versions_cache: tuple[float, list[str]] | None = None
_kernels_cache: dict[str, tuple[float, list["OpenWrtKernelFile"]]] = {}
_CACHE_TTL_SEC = 3600


class OpenWrtError(Exception):
    """OpenWrt 目录/下载失败。"""


@dataclass
class OpenWrtKernelFile:
    name: str
    url: str
    size: int | None = None
    local: bool = False
    local_path: str | None = None


def target_for_arch(arch: str) -> str:
    key = (arch or "").strip().lower()
    target = ARCH_OPENWRT_TARGET.get(key)
    if not target:
        raise OpenWrtError(
            f"架构「{arch}」暂无映射的 OpenWrt target，支持: "
            + ", ".join(sorted(set(ARCH_OPENWRT_TARGET)))
        )
    return target


def kernels_dir() -> Path:
    settings = get_settings()
    path = settings.kernels_path
    path.mkdir(parents=True, exist_ok=True)
    return path


def openwrt_base() -> str:
    return get_settings().OPENWRT_DOWNLOAD_BASE.rstrip("/")


def target_index_url(version: str, arch: str) -> str:
    target = target_for_arch(arch)
    ver = (version or "").strip().rstrip("/")
    if not ver:
        raise OpenWrtError("版本不能为空")
    base = openwrt_base()
    if ver.lower() == "snapshot":
        return f"{base}/snapshots/targets/{target}/"
    return f"{base}/releases/{ver}/targets/{target}/"


def file_download_url(version: str, arch: str, filename: str) -> str:
    return urljoin(target_index_url(version, arch), filename)


def _safe_filename(name: str) -> str:
    raw = unquote((name or "").strip())
    base = Path(raw).name
    if not base or base in (".", "..") or "/" in base or "\\" in base:
        raise OpenWrtError("非法文件名")
    if not re.fullmatch(r"[A-Za-z0-9._+-]+", base):
        raise OpenWrtError(f"文件名包含非法字符: {base}")
    return base


def is_kernel_filename(name: str) -> bool:
    if not name or name.endswith("/"):
        return False
    if _SKIP_NAME_RE.search(name):
        return False
    # 明确排除 initramfs（一般不适合当持久 rootfs 启动内核；仍可选时再放宽）
    lower = name.lower()
    if "initramfs" in lower:
        return False
    if _KERNEL_NAME_RE.search(name):
        return True
    # armsr 等：*kernel.bin
    if "kernel.bin" in lower:
        return True
    return False


def _parse_hrefs(html: str) -> list[str]:
    out: list[str] = []
    for href in _HREF_RE.findall(html):
        href = href.strip()
        if not href or href.startswith(("?", "#", "javascript:", "mailto:")):
            continue
        if href in ("../", "./", "/"):
            continue
        # 绝对站内路径保留末段
        if href.startswith("http://") or href.startswith("https://"):
            # 仅接受同站链接
            if "openwrt.org" not in href and openwrt_base() not in href:
                continue
            href = href.rstrip("/").rsplit("/", 1)[-1] + ("/" if href.endswith("/") else "")
        if href.startswith("/"):
            # /releases/24.10.0/ → 24.10.0/
            parts = [p for p in href.split("/") if p]
            if not parts:
                continue
            href = parts[-1] + ("/" if href.endswith("/") else "")
        out.append(unquote(href))
    return out


def _http_client(*, timeout: float = 30.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout, connect=15.0),
        headers={"User-Agent": "FSEMS/1.0 (+OpenWrt metadata only; binaries only on explicit download)"},
    )


async def _fetch_text(url: str, *, timeout: float = 30.0) -> str:
    """仅拉取文本/JSON 元数据，禁止当作固件下载入口。"""
    try:
        async with _http_client(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()
            # 目录索引或 JSON；若误拿到大体积二进制则拒绝
            clen = resp.headers.get("content-length")
            if clen and clen.isdigit() and int(clen) > 2 * 1024 * 1024:
                raise OpenWrtError(f"元数据响应过大 ({clen} bytes)，已中止: {url}")
            if "octet-stream" in ctype or "application/x-" in ctype:
                raise OpenWrtError(f"期望目录/JSON 元数据，却收到二进制: {url}")
            return resp.text
    except OpenWrtError:
        raise
    except httpx.HTTPError as exc:
        raise OpenWrtError(f"请求 OpenWrt 失败: {url} ({exc})") from exc


async def _fetch_json(url: str, *, timeout: float = 20.0) -> dict | list:
    try:
        async with _http_client(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as exc:
        raise OpenWrtError(f"请求 OpenWrt JSON 失败: {url} ({exc})") from exc
    except ValueError as exc:
        raise OpenWrtError(f"OpenWrt JSON 解析失败: {url}") from exc


def list_local_kernels() -> list[dict]:
    """列出 data/kernels 下已有内核文件。"""
    root = kernels_dir()
    items: list[dict] = []
    for p in sorted(root.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        if p.name.startswith("."):
            continue
        items.append(
            {
                "name": p.name,
                "path": str(p.resolve()),
                "size": p.stat().st_size,
            }
        )
    return items


def local_kernel_path(filename: str) -> Path:
    return (kernels_dir() / _safe_filename(filename)).resolve()


def mark_local(files: list[OpenWrtKernelFile]) -> list[OpenWrtKernelFile]:
    for f in files:
        lp = local_kernel_path(f.name)
        if lp.is_file() and lp.stat().st_size > 0:
            f.local = True
            f.local_path = str(lp)
        else:
            f.local = False
            f.local_path = str(lp)
    return files


async def list_versions(*, force: bool = False) -> list[str]:
    """
    仅拉取版本元数据（默认 .versions.json，约 1KB），不下载任何固件。
    返回列表：snapshot + 官方 versions_list（新→旧）。
    """
    global _versions_cache
    now = time.monotonic()
    if not force and _versions_cache and now - _versions_cache[0] < _CACHE_TTL_SEC:
        return list(_versions_cache[1])

    versions: list[str] = []
    source = "versions.json"
    try:
        # 官方轻量 JSON：https://downloads.openwrt.org/.versions.json
        data = await _fetch_json(f"{openwrt_base()}/.versions.json")
        if isinstance(data, dict):
            raw = data.get("versions_list") or []
            if isinstance(raw, list):
                versions = [str(v).strip().rstrip("/") for v in raw if str(v).strip()]
    except OpenWrtError as exc:
        logger.warning("读取 .versions.json 失败，回退 HTML 目录索引: %s", exc)
        source = "releases_html"
        html = await _fetch_text(f"{openwrt_base()}/releases/")
        for href in _parse_hrefs(html):
            name = href.rstrip("/")
            if name.startswith("packages"):
                continue
            if _VERSION_DIR_RE.match(name + "/") or _VERSION_DIR_RE.match(name):
                versions.append(name)

    def ver_key(v: str) -> tuple:
        m = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?(-rc(\d+))?$", v)
        if not m:
            return (0, 0, 0, 0, v)
        major, minor, patch, _, rc = m.groups()
        return (
            int(major),
            int(minor),
            int(patch or 0),
            1 if rc is None else 0,
            int(rc or 0),
        )

    versions = sorted(set(versions), key=ver_key, reverse=True)
    # 默认只保留较新的条目，避免下拉框塞满历史版本；全量仍可从 JSON 获取
    # versions_list 本身已是官方维护列表，这里再截断过长历史
    max_items = 40
    if len(versions) > max_items:
        versions = versions[:max_items]

    result = ["snapshot", *versions]
    logger.info("OpenWrt 版本元数据已更新 source=%s count=%s", source, len(result))
    _versions_cache = (now, result)
    return list(result)


async def list_kernels(version: str, arch: str, *, force: bool = False) -> list[OpenWrtKernelFile]:
    """
    仅拉取 target 目录索引 HTML，解析内核「文件名列表」。
    不会下载 .bin/.elf 等固件本体；是否已在本地由 data/kernels 判断。
    """
    cache_key = f"{version.strip()}::{arch.strip().lower()}"
    now = time.monotonic()
    if not force and cache_key in _kernels_cache:
        ts, items = _kernels_cache[cache_key]
        if now - ts < _CACHE_TTL_SEC:
            return mark_local([OpenWrtKernelFile(name=i.name, url=i.url, size=i.size) for i in items])

    index = target_index_url(version, arch)
    # 只 GET 目录页（HTML），不请求其中的固件链接
    html = await _fetch_text(index)
    files: list[OpenWrtKernelFile] = []
    seen: set[str] = set()
    for href in _parse_hrefs(html):
        name = href.rstrip("/").rsplit("/", 1)[-1]
        if name in seen or not is_kernel_filename(name):
            continue
        seen.add(name)
        files.append(
            OpenWrtKernelFile(
                name=name,
                url=urljoin(index, name),
            )
        )

    def sort_key(f: OpenWrtKernelFile) -> tuple:
        n = f.name.lower()
        score = 0
        if "generic-kernel.bin" in n or n.endswith("kernel.bin"):
            score -= 10
        if "vmlinux.elf" in n:
            score -= 8
        if "vmlinux.bin" in n:
            score -= 7
        if "vmlinuz" in n:
            score -= 6
        return (score, n)

    files.sort(key=sort_key)
    logger.info(
        "OpenWrt 内核目录索引已解析 version=%s arch=%s files=%s (metadata only)",
        version,
        arch,
        len(files),
    )
    _kernels_cache[cache_key] = (now, files)
    return mark_local(files)


async def download_kernel(version: str, arch: str, filename: str) -> dict:
    """
    【唯一会拉取固件本体的入口】下载内核到 kernels 目录。
    已存在且非空则直接返回本地路径，不重复下载。
    """
    name = _safe_filename(filename)
    # 校验文件名确实出现在该目录（防任意 URL 拼接）
    available = await list_kernels(version, arch)
    match = next((f for f in available if f.name == name), None)
    if not match:
        raise OpenWrtError(f"该版本/架构下未找到内核文件: {name}")

    dest = local_kernel_path(name)
    if dest.is_file() and dest.stat().st_size > 0:
        return {
            "name": name,
            "path": str(dest),
            "size": dest.stat().st_size,
            "downloaded": False,
            "url": match.url,
        }

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()

    logger.info("下载 OpenWrt 内核: %s -> %s", match.url, dest)
    try:
        timeout = httpx.Timeout(600.0, connect=30.0)
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "FSEMS/1.0 (+OpenWrt firmware helper)"},
        ) as client:
            async with client.stream("GET", match.url) as resp:
                resp.raise_for_status()
                with tmp.open("wb") as fh:
                    async for chunk in resp.aiter_bytes(chunk_size=1024 * 256):
                        if chunk:
                            fh.write(chunk)
                            await asyncio.sleep(0)
        if not tmp.is_file() or tmp.stat().st_size <= 0:
            raise OpenWrtError("下载完成但文件为空")
        tmp.replace(dest)
    except OpenWrtError:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    except httpx.HTTPError as exc:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise OpenWrtError(f"下载失败: {exc}") from exc
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise

    return {
        "name": name,
        "path": str(dest.resolve()),
        "size": dest.stat().st_size,
        "downloaded": True,
        "url": match.url,
    }
