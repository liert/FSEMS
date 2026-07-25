# -*- coding: utf-8 -*-
"""
独立启动 Streamable HTTP MCP 服务：

  cd backend && .venv/bin/python -m app.mcp_server

默认监听 MCP_HOST:MCP_PORT（见 .env），路径为 /mcp。
"""
from __future__ import annotations

import logging

from app.core.config import get_settings
from app.core.database import init_db
from app.mcp_server.server import create_mcp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("fsems.mcp")


def main() -> None:
    import asyncio

    settings = get_settings()
    settings.ensure_dirs()

    async def _init() -> None:
        await init_db()

    asyncio.run(_init())

    mcp = create_mcp()
    # 独立进程时使用完整路径 /mcp，便于客户端配置
    mcp.settings.streamable_http_path = "/mcp"
    logger.info(
        "Starting FSEMS MCP Streamable HTTP on http://%s:%s/mcp (stateless=%s)",
        settings.MCP_HOST,
        settings.MCP_PORT,
        settings.MCP_STATELESS,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
