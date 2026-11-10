from __future__ import annotations

from app.mcp.instance import mcp

# Register tools on the shared FastMCP instance.
from app.mcp import tools as _tools  # noqa: F401

__all__ = ["mcp"]
