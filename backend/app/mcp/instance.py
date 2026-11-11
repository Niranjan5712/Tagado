from __future__ import annotations

from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from app.config import get_settings

SERVER_INSTRUCTIONS = (
    "Tagado tracks invoices and sends follow-up emails on the owner's behalf. "
    "Workflow: (1) call get_client_context before drafting for any client; "
    "(2) match tone to history and owner notes: warm for reliable long-term clients, "
    "clear and specific about dates for clients with late payments or broken promises, never threatening; "
    "(3) call create_invoice_with_plan — this also onboards a brand-new client when the email is new; "
    "(4) give the owner the review_url and say nothing is sent until they approve in Tagado. "
    "Use today_ist from tool results for all dates. Never include bank details, payment links, "
    "or legal or tax references in message text; Tagado adds payment details and any legal note itself. "
    "Write in the owner's voice, first person, short paragraphs, Indian English. "
    "Use placeholders for amounts and dates."
)


def _transport_security() -> TransportSecuritySettings:
    """Localhost stays locked down; public HTTPS sits behind the host reverse proxy."""
    settings = get_settings()
    host = urlparse(settings.app_url).hostname or "localhost"
    if settings.app_url.startswith("https://"):
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1",
            "127.0.0.1:*",
            "localhost",
            "localhost:*",
            "[::1]",
            "[::1]:*",
            host,
            f"{host}:*",
        ],
        allowed_origins=[
            "http://127.0.0.1:*",
            "http://localhost:*",
            settings.app_url.rstrip("/"),
        ],
    )


mcp = FastMCP(
    "Tagado",
    instructions=SERVER_INSTRUCTIONS,
    stateless_http=True,
    json_response=True,
    host="0.0.0.0",
    transport_security=_transport_security(),
)
mcp.settings.streamable_http_path = "/"
