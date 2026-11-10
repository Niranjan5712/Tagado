from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.db.models import Invoice, Message
from app.services.money import format_inr, paise_to_inr
from app.services.plans import outstanding_paise
from app.services.stats import workspace_dashboard_totals
from app.services.time import IST, ensure_utc, format_today_ist, today_ist


def review_url(settings: Settings, invoice_id: str) -> str:
    return f"{settings.app_url.rstrip('/')}/invoices/{invoice_id}"


def client_page_url(settings: Settings, public_token: str) -> str:
    return f"{settings.app_url.rstrip('/')}/p/{public_token}"


def list_invoices(
    db: Session,
    workspace_id: str,
    *,
    status: str = "all",
    client: str | None = None,
    settings: Settings,
) -> dict:
    today = today_ist()
    rows = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.workspace_id == workspace_id)
            .options(selectinload(Invoice.client), selectinload(Invoice.messages))
            .order_by(Invoice.due_date.asc())
        )
    )

    filtered: list[Invoice] = []
    for invoice in rows:
        if client:
            needle = client.lower()
            hay = f"{invoice.client.name} {invoice.client.email}".lower()
            if needle not in hay:
                continue
        if not _status_matches(invoice, status, today):
            continue
        filtered.append(invoice)

    totals = workspace_dashboard_totals(db, workspace_id, today=today)
    payload = [_list_row(invoice, today, settings) for invoice in filtered[:50]]
    return {
        "today_ist": format_today_ist(),
        "totals": {
            "outstanding_inr": paise_to_inr(totals["outstanding_paise"]),
            "overdue_inr": paise_to_inr(totals["overdue_paise"]),
            "outstanding_count": totals["outstanding_count"],
            "overdue_count": totals["overdue_count"],
        },
        "invoices": payload,
        "summary": f"{len(payload)} invoice(s); outstanding {format_inr(totals['outstanding_paise'])}.",
    }


def get_invoice(
    db: Session,
    workspace_id: str,
    *,
    invoice_id: str | None = None,
    invoice_number: str | None = None,
    settings: Settings,
) -> dict:
    query = select(Invoice).where(Invoice.workspace_id == workspace_id).options(
        selectinload(Invoice.client),
        selectinload(Invoice.messages),
        selectinload(Invoice.events),
    )
    if invoice_id:
        query = query.where(Invoice.id == invoice_id)
    elif invoice_number:
        query = query.where(Invoice.invoice_number == invoice_number)
    else:
        raise ValueError("Provide invoice_id or invoice_number")

    invoice = db.scalar(query)
    if invoice is None:
        raise ValueError("Invoice not found")

    today = today_ist()
    return {
        "today_ist": format_today_ist(),
        "invoice": {
            "id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "description": invoice.description,
            "amount_inr": paise_to_inr(invoice.amount_paise),
            "outstanding_inr": paise_to_inr(outstanding_paise(invoice)),
            "issue_date": invoice.issue_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "days_overdue": _days_overdue(invoice, today),
            "status": invoice.status,
            "plan_status": invoice.plan_status,
            "promise_date": invoice.promise_date.isoformat() if invoice.promise_date else None,
            "promise_count": invoice.promise_count,
            "promise_broken": invoice.promise_broken,
            "reported_amount_inr": (
                paise_to_inr(invoice.reported_amount_paise)
                if invoice.reported_amount_paise is not None
                else None
            ),
            "reported_reference": invoice.reported_reference,
            "reported_paid_on": invoice.reported_paid_on.isoformat() if invoice.reported_paid_on else None,
            "issue_kind": invoice.issue_kind,
            "issue_reason": invoice.issue_reason,
            "issue_note": invoice.issue_note,
        },
        "client": {
            "id": invoice.client.id,
            "name": invoice.client.name,
            "contact_name": invoice.client.contact_name,
            "email": invoice.client.email,
            "cc_emails": invoice.client.cc_emails or [],
            "relationship_notes": invoice.client.relationship_notes,
        },
        "messages": [_message_row(message) for message in sorted(invoice.messages, key=lambda m: m.step)],
        "events": [
            {
                "actor": event.actor,
                "type": event.type,
                "data": event.data,
                "created_at": ensure_utc(event.created_at).isoformat() if event.created_at else None,
            }
            for event in sorted(
                invoice.events,
                key=lambda event: ensure_utc(event.created_at) or event.created_at,
                reverse=True,
            )[:20]
        ],
        "review_url": review_url(settings, invoice.id),
        "client_page_url": client_page_url(settings, invoice.public_token),
        "summary": (
            f"{invoice.invoice_number} · {invoice.client.name} · "
            f"{format_inr(outstanding_paise(invoice))} · {invoice.status}/{invoice.plan_status}"
        ),
    }


def serialize_created_invoice(
    invoice: Invoice,
    *,
    settings: Settings,
    client_stats: dict | None = None,
    already_tracked: bool = False,
    sunday_shifts: list[dict] | None = None,
) -> dict:
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "client_id": invoice.client_id,
        "client_name": invoice.client.name if invoice.client else None,
        "client_created_or_reused": True,
        "status": invoice.status,
        "plan_status": invoice.plan_status,
        "review_url": review_url(settings, invoice.id),
        "client_page_url": client_page_url(settings, invoice.public_token),
        "messages": [_message_row(message) for message in sorted(invoice.messages, key=lambda m: m.step)],
        "sunday_shifts": sunday_shifts or [],
        "client_stats": client_stats,
        "already_tracked": already_tracked,
        "summary": (
            f"Already tracked {invoice.invoice_number}. Use replace_remaining_messages to change its plan. "
            f"Review: {review_url(settings, invoice.id)}"
            if already_tracked
            else (
                f"Draft plan saved for {invoice.invoice_number} ({invoice.client.name}). "
                f"Nothing is sent until you approve: {review_url(settings, invoice.id)}"
            )
        ),
    }


def _status_matches(invoice: Invoice, status: str, today: date) -> bool:
    key = (status or "all").lower()
    if key in {"", "all"}:
        return True
    if key == "open":
        return invoice.status == "open"
    if key == "overdue":
        return invoice.status in {"open", "promised"} and invoice.due_date < today
    if key == "promised":
        return invoice.status == "promised"
    if key == "issues":
        return invoice.status == "issue_raised"
    if key == "payment_reported":
        return invoice.status == "payment_reported"
    if key == "paid":
        return invoice.status == "paid"
    return invoice.status == key


def _days_overdue(invoice: Invoice, today: date) -> int:
    if invoice.status not in {"open", "promised"}:
        return 0
    return max((today - invoice.due_date).days, 0)


def _next_send(invoice: Invoice) -> str | None:
    scheduled = [
        m
        for m in invoice.messages
        if m.kind == "main" and m.status == "scheduled" and m.send_at is not None
    ]
    if not scheduled:
        held = [m for m in invoice.messages if m.kind == "main" and m.status == "held"]
        if held:
            return "Held"
        return None
    soonest = min(scheduled, key=lambda m: ensure_utc(m.send_at) or m.send_at)
    send_at = ensure_utc(soonest.send_at)
    return send_at.date().isoformat() if send_at else None


def _list_row(invoice: Invoice, today: date, settings: Settings) -> dict:
    return {
        "id": invoice.id,
        "client": invoice.client.name,
        "invoice_number": invoice.invoice_number,
        "amount_inr": paise_to_inr(invoice.amount_paise),
        "outstanding_inr": paise_to_inr(outstanding_paise(invoice)),
        "due_date": invoice.due_date.isoformat(),
        "days_overdue": _days_overdue(invoice, today),
        "status": invoice.status,
        "plan_status": invoice.plan_status,
        "next_send": _next_send(invoice),
        "review_url": review_url(settings, invoice.id),
    }


def _message_row(message: Message) -> dict:
    send_at = ensure_utc(message.send_at)
    return {
        "id": message.id,
        "kind": message.kind,
        "step": message.step,
        "tone": message.tone,
        "subject": message.subject,
        "body": message.body,
        "status": message.status,
        "send_at": send_at.isoformat() if send_at else None,
        "send_on_ist": send_at.astimezone(IST).date().isoformat() if send_at else None,
    }
