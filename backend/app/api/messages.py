from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace
from app.config import get_settings
from app.db.models import Invoice, Message, OutboundEmail, Workspace
from app.db.session import get_db
from app.services.email.compose import compose_message_email
from app.services.scheduler import SendError, send_one_now

router = APIRouter(tags=["messages"])


def _get_workspace_message(
    db: Session,
    workspace: Workspace,
    message_id: str,
) -> Message:
    message = db.scalar(
        select(Message)
        .join(Invoice, Invoice.id == Message.invoice_id)
        .where(Message.id == message_id, Invoice.workspace_id == workspace.id)
        .options(
            selectinload(Message.invoice).selectinload(Invoice.client),
            selectinload(Message.invoice).selectinload(Invoice.workspace),
        )
    )
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


@router.get("/messages/{message_id}/preview")
def preview_message(
    message_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    message = _get_workspace_message(db, workspace, message_id)
    composed = compose_message_email(
        invoice=message.invoice,
        message=message,
        workspace=workspace,
        settings=get_settings(),
    )
    return {
        "message_id": message.id,
        "to": composed.to_addrs,
        "cc": composed.cc_addrs,
        "reply_to": composed.reply_to,
        "from_display": composed.from_display,
        "subject": composed.subject,
        "html": composed.html,
        "text": composed.text,
        "client_page_url": composed.client_page_url,
    }


@router.post("/messages/{message_id}/send-now")
def send_message_now(
    message_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    message = _get_workspace_message(db, workspace, message_id)
    try:
        result = send_one_now(db, message.id, settings=get_settings())
    except SendError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    outbox = None
    if result.get("outbound_email_id"):
        outbox = db.get(OutboundEmail, result["outbound_email_id"])
    return {
        **result,
        "outbox": (
            {
                "id": outbox.id,
                "subject": outbox.subject,
                "to": outbox.to_addrs,
                "created_at": outbox.created_at.isoformat() if outbox.created_at else None,
            }
            if outbox
            else None
        ),
    }
