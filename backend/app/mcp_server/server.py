# -*- coding: utf-8 -*-
"""
FSEMS MCP Server (Streamable HTTP)

协议：MCP Streamable HTTP（官方 mcp SDK FastMCP）
端点：默认挂载在 FastAPI 的 /mcp （POST/GET）

向 LLM Agent 暴露 QEMU/OpenWrt 实例与模板管理能力。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_mcp: FastMCP | None = None


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=str, indent=2)


def create_mcp() -> FastMCP:
    """构建并注册全部工具/资源的 FastMCP 实例。"""
    settings = get_settings()

    # DNS rebinding 防护：开发环境放宽；生产可通过配置收紧
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )

    mcp = FastMCP(
        name="FSEMS",
        instructions=(
            "FSEMS（Firmware Simulation Environment Management System）管理接口。\n"
            "你可以通过本 MCP 工具管理 OpenWrt/IoT 固件的 QEMU 实例生命周期、"
            "查看模板、查询健康状态。\n"
            "注意：启动/停止实例需要宿主机具备 TAP/网桥权限；删除实例不可恢复。"
        ),
        website_url="https://github.com/fsems",
        streamable_http_path="/",  # 由 FastAPI 挂载到 MCP_PATH
        stateless_http=settings.MCP_STATELESS,
        json_response=settings.MCP_JSON_RESPONSE,
        transport_security=security,
    )

    _register_tools(mcp)
    _register_resources(mcp)
    return mcp


def get_mcp() -> FastMCP:
    global _mcp
    if _mcp is None:
        _mcp = create_mcp()
    return _mcp


def mcp_asgi_app():
    """返回 Streamable HTTP ASGI 应用（需在 lifespan 中运行 session_manager）。"""
    return get_mcp().streamable_http_app()


def _register_tools(mcp: FastMCP) -> None:
    from app.mcp_server import tools as t

    @mcp.tool(name="fsems_health", description="检查 FSEMS 服务与依赖（数据库路径、工作空间）健康状态")
    async def fsems_health() -> str:
        return _json(await t.health())

    @mcp.tool(name="list_templates", description="列出固件模板；可按架构过滤，如 aarch64 / mips / mipsel / x86_64")
    async def list_templates(arch: str | None = None) -> str:
        return _json(await t.list_templates(arch))

    @mcp.tool(name="list_instances", description="分页列出 QEMU 实例（id、名称、状态、SSH 地址等）")
    async def list_instances(page: int = 1, limit: int = 20) -> str:
        return _json(await t.list_instances(page=page, limit=limit))

    @mcp.tool(name="get_instance", description="获取实例详情（内存、磁盘、RootFS、模板路径等）")
    async def get_instance(instance_id: str) -> str:
        return _json(await t.get_instance(instance_id))

    @mcp.tool(
        name="create_instance",
        description=(
            "创建实例。需要 name 与 template_id；可选 rootfs_path（自定义 RootFS 源路径）、"
            "network_type=same|different、filesystem_type=ext4|squashfs|f2fs、"
            "use_custom_rootfs=true 时将自定义 RootFS 作为启动盘"
        ),
    )
    async def create_instance(
        name: str,
        template_id: int,
        rootfs_path: str | None = None,
        network_type: str = "same",
        filesystem_type: str = "ext4",
        use_custom_rootfs: bool = False,
    ) -> str:
        return _json(
            await t.create_instance(
                name=name,
                template_id=template_id,
                rootfs_path=rootfs_path,
                network_type=network_type,
                filesystem_type=filesystem_type,
                use_custom_rootfs=use_custom_rootfs,
            )
        )

    @mcp.tool(
        name="instance_action",
        description=(
            "对实例执行生命周期操作：start / stop / reset。wait_boot=true 时等待 SSH 探活；"
            "响应包含 QEMU 命令、进程、串口和网络诊断。"
        ),
    )
    async def instance_action(
        instance_id: str,
        action: str,
        allow_sigkill: bool = True,
        wait_boot: bool = False,
    ) -> str:
        return _json(
            await t.instance_action(
                instance_id,
                action,
                allow_sigkill=allow_sigkill,
                wait_boot=wait_boot,
            )
        )

    @mcp.tool(
        name="instance_diagnostics",
        description=(
            "获取实例启动诊断：QEMU 命令/退出码/stderr、串口尾部、内核和磁盘格式、"
            "TAP/网桥及 SSH 状态。"
        ),
    )
    async def instance_diagnostics(instance_id: str, serial_lines: int = 200) -> str:
        return _json(await t.instance_diagnostics(instance_id, serial_lines=serial_lines))

    @mcp.tool(name="delete_instance", description="彻底删除实例及其工作空间、磁盘与 TAP 资源（不可恢复）")
    async def delete_instance(instance_id: str) -> str:
        return _json(await t.delete_instance(instance_id))

    @mcp.tool(
        name="update_custom_rootfs",
        description="修改实例自定义 RootFS 源路径并重新解压；rootfs_path 为空则清除",
    )
    async def update_custom_rootfs(instance_id: str, rootfs_path: str | None = None) -> str:
        return _json(await t.update_custom_rootfs(instance_id, rootfs_path))

    @mcp.tool(name="list_snapshots", description="列出实例的 qcow2 快照")
    async def list_snapshots(instance_id: str) -> str:
        return _json(await t.list_snapshots(instance_id))


def _register_resources(mcp: FastMCP) -> None:
    from app.mcp_server import tools as t

    @mcp.resource("fsems://health", name="health", description="服务健康状态 JSON", mime_type="application/json")
    async def res_health() -> str:
        return _json(await t.health())

    @mcp.resource("fsems://instances", name="instances", description="当前实例列表 JSON", mime_type="application/json")
    async def res_instances() -> str:
        return _json(await t.list_instances(page=1, limit=100))

    @mcp.resource("fsems://templates", name="templates", description="模板列表 JSON", mime_type="application/json")
    async def res_templates() -> str:
        return _json(await t.list_templates(None))
