# -*- coding: utf-8 -*-
"""FSEMS Streamable HTTP MCP Server — 为 Agent 提供实例/模板管理工具。"""

from app.mcp_server.server import create_mcp, get_mcp, mcp_asgi_app

__all__ = ["create_mcp", "get_mcp", "mcp_asgi_app"]
