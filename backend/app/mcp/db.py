from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session

from app.db import session as db_session
from app.db.models import Workspace
from app.mcp.context import require_workspace_id


@contextmanager
def workspace_db() -> Generator[tuple[Session, Workspace], None, None]:
    workspace_id = require_workspace_id()
    db = db_session.SessionLocal()
    try:
        workspace = db.get(Workspace, workspace_id)
        if workspace is None:
            raise RuntimeError("Workspace not found for MCP token")
        yield db, workspace
    finally:
        db.close()
