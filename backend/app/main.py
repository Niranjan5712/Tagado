from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.api import api_router
from app.config import get_settings
from app.db.session import SessionLocal, init_db
from app.mcp.auth_middleware import McpTokenMiddleware
from app.mcp.server import mcp
from app.services.seed import ensure_demo_workspace

logger = logging.getLogger("tagado")

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        workspace = ensure_demo_workspace(db, settings)
        mcp_url = f"{settings.app_url.rstrip('/')}/mcp/?key={workspace.mcp_token}"
        logger.warning("Tagado ready | demo=%s | mcp=%s", settings.demo_email, mcp_url)
    finally:
        db.close()

    async with mcp.session_manager.run():
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Tagado", lifespan=lifespan)
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="tagado_session",
        same_site="lax",
        https_only=settings.app_url.startswith("https://"),
    )
    application.include_router(api_router, prefix="/api")
    application.mount("/mcp", McpTokenMiddleware(mcp.streamable_http_app()))

    if FRONTEND_DIST.exists():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.exists():
            application.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @application.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            if full_path.startswith(("api/", "mcp")):
                return FileResponse(FRONTEND_DIST / "index.html", status_code=404)
            candidate = FRONTEND_DIST / full_path
            if full_path and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return application


app = create_app()
