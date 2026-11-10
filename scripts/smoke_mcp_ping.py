#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.seed import ensure_demo_workspace


async def call_ping(mcp_url: str) -> None:
    async with streamablehttp_client(mcp_url) as (read, write, _get_session_id):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("tools:", [tool.name for tool in tools.tools])
            result = await session.call_tool("ping", {})
            print("ping_content:", result.content)
            if result.structuredContent is not None:
                print("ping_structured:", result.structuredContent)


def main() -> int:
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        workspace = ensure_demo_workspace(db, settings)
        mcp_url = f"{settings.app_url.rstrip('/')}/mcp/?key={workspace.mcp_token}"
    finally:
        db.close()

    # Prefer loopback for local smoke even if APP_URL uses localhost hostname
    mcp_url = mcp_url.replace("://localhost:", "://127.0.0.1:")
    print("mcp_url:", mcp_url)
    asyncio.run(call_ping(mcp_url))
    return 0


if __name__ == "__main__":
    sys.exit(main())
