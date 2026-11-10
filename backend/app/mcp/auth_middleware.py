from __future__ import annotations

from urllib.parse import parse_qs

from starlette.types import ASGIApp, Receive, Scope, Send

from app.db.session import SessionLocal
from app.mcp.context import current_workspace_id, current_workspace_name
from app.services.seed import get_workspace_by_mcp_token


class McpTokenMiddleware:
    """Resolve ?key= to a workspace before the MCP ASGI app handles the request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        query = parse_qs(scope.get("query_string", b"").decode("utf-8"))
        token_values = query.get("key") or []
        token = token_values[0] if token_values else ""

        if not token:
            await self._unauthorized(send, "Missing MCP key. Use /mcp/?key=<workspace-token>")
            return

        db = SessionLocal()
        try:
            workspace = get_workspace_by_mcp_token(db, token)
        finally:
            db.close()

        if workspace is None:
            await self._unauthorized(send, "Invalid MCP key")
            return

        ws_id_token = current_workspace_id.set(workspace.id)
        ws_name_token = current_workspace_name.set(workspace.business_name)
        try:
            await self.app(scope, receive, send)
        finally:
            current_workspace_id.reset(ws_id_token)
            current_workspace_name.reset(ws_name_token)

    async def _unauthorized(self, send: Send, detail: str) -> None:
        body = detail.encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
