from __future__ import annotations

from mcp.server.fastmcp import FastMCP

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

mcp = FastMCP(
    "Tagado",
    instructions=SERVER_INSTRUCTIONS,
    stateless_http=True,
    json_response=True,
)
mcp.settings.streamable_http_path = "/"
