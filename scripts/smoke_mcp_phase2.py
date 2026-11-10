#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import sys
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import get_settings
from app.db.session import SessionLocal, init_db
from app.services.seed import ensure_demo_workspace
from app.services.time import today_ist


def parse_result(result) -> dict:
    if result.structuredContent:
        return result.structuredContent
    for item in result.content or []:
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
    return {"isError": result.isError, "content": str(result.content)}


async def main() -> None:
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        workspace = ensure_demo_workspace(db, settings)
        mcp_url = f"http://127.0.0.1:8000/mcp/?key={workspace.mcp_token}"
    finally:
        db.close()

    today = today_ist()
    async with streamablehttp_client(mcp_url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = sorted(tool.name for tool in tools.tools)
            print("tools:", names)

            ctx = parse_result(await session.call_tool("get_client_context", {"query": "Aarohan"}))
            print("aarohan_found:", ctx.get("found"))
            print("aarohan_summary:", ctx.get("summary"))

            created = parse_result(
                await session.call_tool(
                    "create_invoice_with_plan",
                    {
                        "client": {
                            "name": "Malabar Crafts Co",
                            "contact_name": "Arjun Pillai",
                            "email": "arjun.pillai@malabar-crafts.example",
                            "cc_emails": [],
                            "notes": "First invoice for this client.",
                        },
                        "invoice": {
                            "invoice_number": f"PX-88{today.day:02d}{today.month:02d}",
                            "amount_inr": 64000,
                            "issue_date": today.isoformat(),
                            "due_date": (today + timedelta(days=16)).isoformat(),
                            "description": "Catalogue design",
                        },
                        "messages": [
                            {
                                "send_on": (today + timedelta(days=2)).isoformat(),
                                "tone": "friendly",
                                "subject": "About {{invoice_number}}",
                                "body": "Hi {{contact_name}}, {{invoice_number}} for {{amount}} is due on {{due_date}}.",
                            },
                            {
                                "send_on": (today + timedelta(days=5)).isoformat(),
                                "tone": "neutral",
                                "subject": "Follow-up on {{invoice_number}}",
                                "body": "Hi {{contact_name}}, checking if {{invoice_number}} is lined up.",
                            },
                            {
                                "send_on": (today + timedelta(days=9)).isoformat(),
                                "tone": "firm",
                                "subject": "Payment date for {{invoice_number}}",
                                "body": "Hi {{contact_name}}, please share a date for {{outstanding}}.",
                            },
                        ],
                        "promise_checkin": {
                            "subject": "Checking {{promise_date}}",
                            "body": "Hi {{contact_name}}, checking whether {{invoice_number}} went out on {{promise_date}}.",
                        },
                    },
                )
            )
            print("create_keys:", sorted(created.keys()))
            print("create_summary:", created.get("summary"))
            print("client_name:", created.get("client_name"))
            print("already_tracked:", created.get("already_tracked"))


if __name__ == "__main__":
    asyncio.run(main())
