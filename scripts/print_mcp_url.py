#!/usr/bin/env python3
"""Print the demo workspace MCP URL from the local SQLite DB (no hardcoded tokens)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db.models import User, Workspace  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.services.seed import ensure_demo_workspace  # noqa: E402


def main() -> int:
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        workspace = ensure_demo_workspace(db, settings)
        user = db.scalar(select(User).where(User.email == settings.demo_email))
        mcp_url = f"{settings.app_url.rstrip('/')}/mcp/?key={workspace.mcp_token}"
        print(f"business: {workspace.business_name}")
        print(f"demo_email: {settings.demo_email}")
        print(f"owner: {user.name if user else ''}")
        print(f"mcp_url: {mcp_url}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
