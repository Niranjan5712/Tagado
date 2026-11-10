from __future__ import annotations

from contextvars import ContextVar

current_workspace_id: ContextVar[str | None] = ContextVar("current_workspace_id", default=None)
current_workspace_name: ContextVar[str | None] = ContextVar("current_workspace_name", default=None)


def require_workspace_id() -> str:
    workspace_id = current_workspace_id.get()
    if not workspace_id:
        raise RuntimeError("MCP workspace context is missing")
    return workspace_id
