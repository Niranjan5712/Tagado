from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Invoice, OutboundEmail, Workspace


def queue_owner_notice(
    db: Session,
    *,
    workspace: Workspace,
    invoice: Invoice,
    subject: str,
    body: str,
) -> OutboundEmail:
    if not workspace.reply_to_email:
        raise ValueError("Workspace reply-to email is required to notify the owner")

    settings = get_settings()
    review_url = f"{settings.app_url.rstrip('/')}/invoices/{invoice.id}"
    full_text = f"{body}\n\nOpen in Tagado: {review_url}"
    html = (
        f"<p>{body}</p>"
        f'<p><a href="{review_url}">Confirm in Tagado</a></p>'
    )

    email = OutboundEmail(
        workspace_id=workspace.id,
        invoice_id=invoice.id,
        message_id=None,
        to_addrs=[workspace.reply_to_email],
        cc_addrs=[],
        reply_to=workspace.reply_to_email,
        subject=subject,
        html=html,
        text=full_text,
        kind="owner_notice",
    )
    db.add(email)
    return email
