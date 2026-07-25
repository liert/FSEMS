# -*- coding: utf-8 -*-
"""
可编辑系统设置持久化。

覆盖项写入 data/settings.override.json，在 get_settings() 中合并。
密码类字段仅在请求显式提供时更新；空字符串表示不修改。
"""
from __future__ import annotations

import json
import logging
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OVERRIDE_PATH = _REPO_ROOT / "data" / "settings.override.json"
_lock = threading.Lock()

# 前端字段 → Settings 模型字段（可写）
EDITABLE_FIELDS: dict[str, str] = {
    "workspace": "FSEMS_WORKSPACE",
    "kernels_dir": "FSEMS_KERNELS_DIR",
    "rootfs_dir": "FSEMS_ROOTFS_DIR",
    "mnt_dir": "FSEMS_MNT_DIR",
    "logs_dir": "LOGS_DIR",
    "bridge": "FSEMS_BRIDGE",
    "boot_timeout_sec": "BOOT_TIMEOUT_SEC",
    "qemu_serial_dir": "QEMU_SERIAL_DIR",
    "fsems_user": "FSEMS_USER",
    "guest_ssh_user": "FSEMS_GUEST_SSH_USER",
    "guest_ssh_password": "FSEMS_GUEST_SSH_PASSWORD",
    "openwrt_download_base": "OPENWRT_DOWNLOAD_BASE",
    "mcp_enabled": "MCP_ENABLED",
    "mcp_path": "MCP_PATH",
    "mcp_host": "MCP_HOST",
    "mcp_port": "MCP_PORT",
    "mcp_stateless": "MCP_STATELESS",
    "mcp_token": "MCP_TOKEN",
    "admin_user": "FSEMS_ADMIN_USER",
    "admin_password": "FSEMS_ADMIN_PASSWORD",
    "jwt_expire_seconds": "JWT_EXPIRE_SECONDS",
    "api_host": "API_HOST",
    "api_port": "API_PORT",
    "redis_url": "REDIS_URL",
}

# 这些字段若提交为空字符串则「不修改」
SECRET_FIELDS = {"guest_ssh_password", "admin_password", "mcp_token", "redis_url"}


def override_path() -> Path:
    return _OVERRIDE_PATH


def load_overrides() -> dict[str, Any]:
    path = _OVERRIDE_PATH
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception as exc:
        logger.warning("读取设置覆盖文件失败 %s: %s", path, exc)
        return {}


def save_overrides(data: dict[str, Any]) -> None:
    path = _OVERRIDE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with _lock:
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
        tmp.replace(path)
    logger.info("系统设置已写入 %s keys=%s", path, list(data.keys()))


def merge_settings_dict(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """将覆盖字典（Settings 字段名）合并到 base model_dump。"""
    out = dict(base)
    for key, value in overrides.items():
        if key in out or key in set(EDITABLE_FIELDS.values()):
            out[key] = value
    return out


def apply_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """
    应用前端提交的 patch（API 字段名），写回覆盖文件，返回完整 Settings 字段覆盖集。
    secret 字段空字符串 = 跳过；明确传 null 可清空（除密码建议用空跳过）。
    """
    current = load_overrides()
    for api_key, model_key in EDITABLE_FIELDS.items():
        if api_key not in patch:
            continue
        value = patch[api_key]
        if api_key in SECRET_FIELDS:
            # 未填则保留原覆盖或 env 默认（不写覆盖）
            if value is None:
                current.pop(model_key, None)
                continue
            if isinstance(value, str) and value.strip() == "":
                continue
            current[model_key] = value
            continue

        if value is None:
            current.pop(model_key, None)
            continue
        current[model_key] = value

    # 校验部分字段
    if "BOOT_TIMEOUT_SEC" in current:
        v = int(current["BOOT_TIMEOUT_SEC"])
        if v < 10 or v > 3600:
            raise ValueError("boot_timeout_sec 须在 10–3600 之间")
        current["BOOT_TIMEOUT_SEC"] = v
    if "JWT_EXPIRE_SECONDS" in current:
        v = int(current["JWT_EXPIRE_SECONDS"])
        if v < 60 or v > 86400 * 30:
            raise ValueError("jwt_expire_seconds 须在 60–2592000 之间")
        current["JWT_EXPIRE_SECONDS"] = v
    if "MCP_PORT" in current:
        v = int(current["MCP_PORT"])
        if v < 1 or v > 65535:
            raise ValueError("mcp_port 无效")
        current["MCP_PORT"] = v
    if "API_PORT" in current:
        v = int(current["API_PORT"])
        if v < 1 or v > 65535:
            raise ValueError("api_port 无效")
        current["API_PORT"] = v
    if "MCP_PATH" in current:
        p = str(current["MCP_PATH"]).strip() or "/mcp"
        if not p.startswith("/"):
            p = "/" + p
        current["MCP_PATH"] = p
    if "MCP_ENABLED" in current:
        current["MCP_ENABLED"] = bool(current["MCP_ENABLED"])
    if "MCP_STATELESS" in current:
        current["MCP_STATELESS"] = bool(current["MCP_STATELESS"])

    save_overrides(current)
    return current
