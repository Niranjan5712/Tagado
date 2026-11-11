from __future__ import annotations

from app.config import Settings, get_settings
from app.db.models import Event, Invoice, Message, OutboundEmail, Workspace
from app.services.money import format_inr_display, paise_to_inr
from app.services.plans import outstanding_paise
from app.services.time import IST, ensure_utc, today_ist


def serialize_workspace_settings(workspace: Workspace, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    mcp_url = f"{settings.app_url.rstrip('/')}/mcp/?key={workspace.mcp_token}"
    return {
        "business_name": workspace.business_name,
        "sender_name": workspace.sender_name,
        "reply_to_email": workspace.reply_to_email,
        "bank_account_name": workspace.bank_account_name,
        "bank_account_number": workspace.bank_account_number,
        "ifsc": workspace.ifsc,
        "upi_id": workspace.upi_id,
        "udyam_number": workspace.udyam_number,
        "send_hour_ist": workspace.send_hour_ist,
        "send_minute_ist": workspace.send_minute_ist,
        "logo_data_url": workspace.logo_data_url,
        "favicon_data_url": workspace.favicon_data_url,
        "accent_color": workspace.accent_color or "#0f6e56",
        "retention_days_paid": workspace.retention_days_paid,
        "retention_keep_audit": workspace.retention_keep_audit,
        "is_demo": workspace.is_demo,
        "claude_connection_url": mcp_url,
        "msme_note_preview": (
            f"{workspace.business_name} is registered as a micro/small enterprise "
            f"(Udyam {workspace.udyam_number}). Under the MSMED Act, payments to registered "
            "micro and small enterprises are due within the agreed period, not exceeding 45 days."
            if workspace.udyam_number
            else None
        ),
    }


def serialize_message(message: Message) -> dict:
    send_at = ensure_utc(message.send_at)
    return {
        "id": message.id,
        "kind": message.kind,
        "step": message.step,
        "tone": message.tone,
        "subject": message.subject,
        "body": message.body,
        "status": message.status,
        "include_msme_note": message.include_msme_note,
        "send_at": send_at.isoformat() if send_at else None,
        "send_on": send_at.astimezone(IST).date().isoformat() if send_at else None,
        "sent_at": ensure_utc(message.sent_at).isoformat() if message.sent_at else None,
        "sent_to": message.sent_to,
        "error": message.error,
    }


def serialize_event(event: Event) -> dict:
    created = ensure_utc(event.created_at)
    return {
        "id": event.id,
        "actor": event.actor,
        "type": event.type,
        "data": event.data,
        "created_at": created.isoformat() if created else None,
    }


def serialize_outbox(row: OutboundEmail) -> dict:
    created = ensure_utc(row.created_at)
    return {
        "id": row.id,
        "kind": row.kind,
        "subject": row.subject,
        "to": row.to_addrs,
        "cc": row.cc_addrs,
        "html": row.html,
        "text": row.text,
        "message_id": row.message_id,
        "created_at": created.isoformat() if created else None,
    }


def serialize_invoice_summary(invoice: Invoice) -> dict:
    today = today_ist()
    days_overdue = 0
    if invoice.status in {"open", "promised"} and invoice.due_date < today:
        days_overdue = (today - invoice.due_date).days

    next_send = None
    scheduled = [
        m for m in invoice.messages if m.kind == "main" and m.status == "scheduled" and m.send_at
    ]
    held = [m for m in invoice.messages if m.kind == "main" and m.status == "held"]
    if scheduled:
        soonest = min(scheduled, key=lambda m: ensure_utc(m.send_at) or m.send_at)
        send_at = ensure_utc(soonest.send_at)
        next_send = send_at.astimezone(IST).date().isoformat() if send_at else None
    elif held:
        next_send = "Held"

    return {
        "id": invoice.id,
        "client_name": invoice.client.name if invoice.client else "",
        "invoice_number": invoice.invoice_number,
        "amount_inr": paise_to_inr(invoice.amount_paise),
        "amount_display": format_inr_display(invoice.amount_paise),
        "outstanding_inr": paise_to_inr(outstanding_paise(invoice)),
        "outstanding_display": format_inr_display(outstanding_paise(invoice)),
        "due_date": invoice.due_date.isoformat(),
        "days_overdue": days_overdue,
        "status": invoice.status,
        "plan_status": invoice.plan_status,
        "next_reminder": next_send,
    }


def serialize_invoice_detail(
    invoice: Invoice,
    *,
    outbox: list[OutboundEmail] | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    summary = serialize_invoice_summary(invoice)
    return {
        **summary,
        "description": invoice.description,
        "issue_date": invoice.issue_date.isoformat(),
        "invoice_url": invoice.invoice_url,
        "public_token": invoice.public_token,
        "client_page_url": f"{settings.app_url.rstrip('/')}/p/{invoice.public_token}",
        "client": {
            "id": invoice.client.id,
            "name": invoice.client.name,
            "contact_name": invoice.client.contact_name,
            "email": invoice.client.email,
            "cc_emails": invoice.client.cc_emails or [],
            "relationship_notes": invoice.client.relationship_notes,
        },
        "promise_date": invoice.promise_date.isoformat() if invoice.promise_date else None,
        "promise_count": invoice.promise_count,
        "promise_broken": invoice.promise_broken,
        "reported_amount_display": (
            format_inr_display(invoice.reported_amount_paise)
            if invoice.reported_amount_paise is not None
            else None
        ),
        "reported_reference": invoice.reported_reference,
        "reported_paid_on": invoice.reported_paid_on.isoformat() if invoice.reported_paid_on else None,
        "reported_at": ensure_utc(invoice.reported_at).isoformat() if invoice.reported_at else None,
        "issue_kind": invoice.issue_kind,
        "issue_reason": invoice.issue_reason,
        "issue_note": invoice.issue_note,
        "paid_at": ensure_utc(invoice.paid_at).isoformat() if invoice.paid_at else None,
        "messages": [serialize_message(m) for m in sorted(invoice.messages, key=lambda m: m.step)],
        "events": [
            serialize_event(e)
            for e in sorted(
                invoice.events,
                key=lambda e: ensure_utc(e.created_at) or e.created_at,
                reverse=True,
            )
        ],
        "outbox": [serialize_outbox(row) for row in (outbox or [])],
        "workspace_has_udyam": bool(invoice.workspace.udyam_number if invoice.workspace else False),
    }
