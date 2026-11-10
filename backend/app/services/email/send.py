from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import OutboundEmail


@dataclass
class SendResult:
    outbound_email_id: str
    to_addrs: list[str]
    subject: str


def send_email(
    db: Session,
    *,
    workspace_id: str,
    invoice_id: str | None,
    message_id: str | None,
    to_addrs: list[str],
    cc_addrs: list[str],
    reply_to: str | None,
    subject: str,
    html: str,
    text: str,
    kind: str = "reminder",
) -> SendResult:
    """
    Assignment send path: persist to Outbox instead of SMTP.
    Swap the body of this function later for Resend/SMTP without changing callers.
    """
    if not to_addrs:
        raise ValueError("At least one recipient is required")

    row = OutboundEmail(
        workspace_id=workspace_id,
        invoice_id=invoice_id,
        message_id=message_id,
        to_addrs=to_addrs,
        cc_addrs=cc_addrs,
        reply_to=reply_to,
        subject=subject,
        html=html,
        text=text,
        kind=kind,
    )
    db.add(row)
    db.flush()
    return SendResult(
        outbound_email_id=row.id,
        to_addrs=to_addrs,
        subject=subject,
    )
