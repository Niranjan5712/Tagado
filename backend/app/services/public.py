from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event, Invoice
from app.services.money import format_inr_display, paise_to_inr
from app.services.plans import outstanding_paise
from app.services.time import ensure_utc, now_utc, today_ist

UPI_MAX_PAISE = 1_00_000_00  # ₹1,00,000


def get_invoice_by_token(db: Session, token: str) -> Invoice | None:
    if not token or len(token) < 16:
        return None
    return db.scalar(
        select(Invoice)
        .where(Invoice.public_token == token)
        .options(
            selectinload(Invoice.client),
            selectinload(Invoice.workspace),
            selectinload(Invoice.events),
        )
    )


def log_client_view(db: Session, invoice: Invoice) -> None:
    cutoff = now_utc() - timedelta(hours=1)
    recent = [
        event
        for event in invoice.events
        if event.type == "client_viewed" and ensure_utc(event.created_at) and ensure_utc(event.created_at) >= cutoff
    ]
    if recent:
        return
    db.add(
        Event(
            invoice_id=invoice.id,
            actor="client",
            type="client_viewed",
            data=None,
        )
    )
    db.commit()


def recently_same_response(db: Session, invoice: Invoice, event_type: str) -> bool:
    cutoff = now_utc() - timedelta(seconds=60)
    return any(
        event.type == event_type
        and ensure_utc(event.created_at) is not None
        and ensure_utc(event.created_at) >= cutoff
        for event in invoice.events
    )


def upi_allowed(invoice: Invoice) -> bool:
    workspace = invoice.workspace
    if not workspace or not workspace.upi_id:
        return False
    if outstanding_paise(invoice) <= 0:
        return False
    return outstanding_paise(invoice) <= UPI_MAX_PAISE


def status_line(invoice: Invoice) -> str:
    today = today_ist()
    business = invoice.workspace.business_name if invoice.workspace else "the business"

    if invoice.status == "paid":
        return "Paid — thank you"
    if invoice.status == "cancelled":
        return "This request was withdrawn"
    if invoice.status == "payment_reported":
        when = invoice.reported_paid_on.isoformat() if invoice.reported_paid_on else "recently"
        return f"Payment reported on {when} — awaiting confirmation from {business}"
    if invoice.status == "promised" and invoice.promise_date:
        return f"Payment scheduled for {invoice.promise_date.isoformat()} — waiting for confirmation"
    if invoice.status == "issue_raised":
        return f"We shared your note with {business}. Reminders are paused for now."

    if invoice.due_date < today:
        days = (today - invoice.due_date).days
        return f"{days} day{'s' if days != 1 else ''} overdue"
    if invoice.due_date == today:
        return "Due today"
    days = (invoice.due_date - today).days
    return f"Due in {days} day{'s' if days != 1 else ''}"


def can_respond(invoice: Invoice) -> bool:
    return invoice.status in {"open", "promised"}


def public_payload(invoice: Invoice) -> dict:
    workspace = invoice.workspace
    outstanding = outstanding_paise(invoice)
    has_bank = bool(
        workspace
        and workspace.bank_account_name
        and workspace.bank_account_number
        and workspace.ifsc
    )
    return {
        "business_name": workspace.business_name if workspace else "",
        "reply_to_email": workspace.reply_to_email if workspace else None,
        "invoice_number": invoice.invoice_number,
        "description": invoice.description,
        "amount_display": format_inr_display(invoice.amount_paise),
        "outstanding_display": format_inr_display(outstanding),
        "outstanding_inr": paise_to_inr(outstanding),
        "due_date": invoice.due_date.isoformat(),
        "status": invoice.status,
        "status_line": status_line(invoice),
        "invoice_url": invoice.invoice_url,
        "can_respond": can_respond(invoice),
        "bank": (
            {
                "account_name": workspace.bank_account_name,
                "account_number": workspace.bank_account_number,
                "ifsc": workspace.ifsc,
            }
            if has_bank and workspace
            else None
        ),
        "upi_available": upi_allowed(invoice),
        "reported_paid_on": invoice.reported_paid_on.isoformat() if invoice.reported_paid_on else None,
        "promise_date": invoice.promise_date.isoformat() if invoice.promise_date else None,
        "issue_reason": invoice.issue_reason,
    }
