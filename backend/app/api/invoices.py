from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace
from app.config import get_settings
from app.db.models import Invoice, Message, OutboundEmail, Workspace
from app.db.session import get_db
from app.services.engine import (
    EngineError,
    approve_plan,
    cancel_invoice,
    confirm_payment,
    pause_plan,
    reject_payment_report,
    resolve_issue_and_resume,
    resume_plan,
    update_message,
)
from app.services.serialize import serialize_invoice_detail, serialize_invoice_summary

router = APIRouter(tags=["invoices"])


class MessagePatch(BaseModel):
    subject: str | None = Field(default=None, max_length=120)
    body: str | None = Field(default=None, max_length=1500)
    send_on: date | None = None
    include_msme_note: bool | None = None


def _load_invoice(db: Session, workspace_id: str, invoice_id: str) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id, Invoice.workspace_id == workspace_id)
        .options(
            selectinload(Invoice.client),
            selectinload(Invoice.messages),
            selectinload(Invoice.events),
            selectinload(Invoice.workspace),
        )
    )
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


def _detail_response(db: Session, invoice: Invoice) -> dict:
    outbox = list(
        db.scalars(
            select(OutboundEmail)
            .where(OutboundEmail.invoice_id == invoice.id)
            .order_by(OutboundEmail.created_at.desc())
        )
    )
    # reload with relationships
    loaded = _load_invoice(db, invoice.workspace_id, invoice.id)
    return serialize_invoice_detail(loaded, outbox=outbox, settings=get_settings())


@router.get("/invoices")
def list_invoices(
    status_filter: str | None = Query(default="all", alias="status"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.workspace_id == workspace.id)
            .options(selectinload(Invoice.client), selectinload(Invoice.messages))
            .order_by(Invoice.due_date.asc())
        )
    )
    from app.services.invoices import _status_matches
    from app.services.time import today_ist

    today = today_ist()
    key = status_filter or "all"
    filtered = [inv for inv in invoices if _status_matches(inv, key, today)]
    return {"invoices": [serialize_invoice_summary(inv) for inv in filtered]}


@router.get("/invoices/{invoice_id}")
def get_invoice(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    invoice = _load_invoice(db, workspace.id, invoice_id)
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/approve")
def approve(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = approve_plan(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/pause")
def pause(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = pause_plan(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/resume")
def resume(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = resume_plan(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/cancel")
def cancel(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = cancel_invoice(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/confirm-payment")
def confirm(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = confirm_payment(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/reject-payment")
def reject(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = reject_payment_report(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.post("/invoices/{invoice_id}/resolve-issue")
def resolve(
    invoice_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    _load_invoice(db, workspace.id, invoice_id)
    try:
        invoice = resolve_issue_and_resume(db, invoice_id)
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _detail_response(db, invoice)


@router.patch("/messages/{message_id}")
def patch_message(
    message_id: str,
    payload: MessagePatch,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    message = db.scalar(
        select(Message)
        .join(Invoice, Invoice.id == Message.invoice_id)
        .where(Message.id == message_id, Invoice.workspace_id == workspace.id)
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    try:
        update_message(
            db,
            message_id,
            subject=payload.subject,
            body=payload.body,
            send_on=payload.send_on,
            actor="owner",
        )
        if payload.include_msme_note is not None:
            msg = db.get(Message, message_id)
            if msg is None:
                raise HTTPException(status_code=404, detail="Message not found")
            if not workspace.udyam_number and payload.include_msme_note:
                raise HTTPException(
                    status_code=400,
                    detail="Add your Udyam number in Settings before enabling the MSME note",
                )
            msg.include_msme_note = payload.include_msme_note
            db.commit()
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    invoice = _load_invoice(db, workspace.id, message.invoice_id)
    return _detail_response(db, invoice)


@router.delete("/messages/{message_id}")
def delete_message(
    message_id: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    message = db.scalar(
        select(Message)
        .join(Invoice, Invoice.id == Message.invoice_id)
        .where(Message.id == message_id, Invoice.workspace_id == workspace.id)
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.kind != "main":
        raise HTTPException(status_code=400, detail="Only follow-up messages can be deleted")
    if message.status not in {"draft", "scheduled", "held"}:
        raise HTTPException(status_code=400, detail="This message can no longer be deleted")

    invoice_id = message.invoice_id
    message.status = "cancelled"
    db.commit()
    invoice = _load_invoice(db, workspace.id, invoice_id)
    return _detail_response(db, invoice)
