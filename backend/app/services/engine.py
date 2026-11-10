from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Client, Event, Invoice, Message, Workspace
from app.services.notifications import queue_owner_notice
from app.services.plans import (
    ComputedMessage,
    DraftMessageInput,
    PlanValidationError,
    PromiseCheckinInput,
    bump_past_send_ats,
    outstanding_paise,
    respace_held_messages,
    validate_and_compute_messages,
)
from app.services.time import now_utc, send_at_for_date, today_ist

UNSENT_STATUSES = {"draft", "scheduled", "held", "sending", "failed"}
EDITABLE_OWNER_STATUSES = {"draft", "scheduled", "held"}


class EngineError(ValueError):
    pass


class DuplicateInvoiceError(EngineError):
    def __init__(self, invoice: Invoice):
        self.invoice = invoice
        super().__init__(
            f"Already tracked; invoice_id={invoice.id}; use replace_remaining_messages to change its plan."
        )


def _load_invoice(db: Session, invoice_id: str) -> Invoice:
    invoice = db.scalar(
        select(Invoice)
        .where(Invoice.id == invoice_id)
        .options(
            selectinload(Invoice.messages),
            selectinload(Invoice.client),
            selectinload(Invoice.workspace),
            selectinload(Invoice.events),
        )
    )
    if invoice is None:
        raise EngineError("Invoice not found")
    return invoice


def _add_event(
    db: Session,
    invoice: Invoice,
    *,
    actor: str,
    event_type: str,
    data: dict[str, Any] | None = None,
) -> None:
    db.add(
        Event(
            invoice_id=invoice.id,
            actor=actor,
            type=event_type,
            data=data,
        )
    )


def _public_token() -> str:
    return secrets.token_urlsafe(24)


def _hold_scheduled(messages: list[Message]) -> None:
    for message in messages:
        if message.status == "scheduled":
            message.status = "held"


def _cancel_unsent(messages: list[Message]) -> int:
    cancelled = 0
    for message in messages:
        if message.status in UNSENT_STATUSES and message.status != "sent":
            if message.status != "cancelled":
                message.status = "cancelled"
                cancelled += 1
    return cancelled


def _upsert_client(
    db: Session,
    *,
    workspace_id: str,
    client_id: str | None,
    name: str,
    contact_name: str,
    email: str,
    cc_emails: list[str] | None,
    notes: str | None,
) -> Client:
    if client_id:
        client = db.get(Client, client_id)
        if client is None or client.workspace_id != workspace_id:
            raise EngineError("client_id not found in this workspace")
        return client

    normalized_email = email.strip().lower()
    existing = db.scalar(
        select(Client).where(
            Client.workspace_id == workspace_id,
            Client.email == normalized_email,
        )
    )
    if existing:
        if notes and not existing.relationship_notes:
            existing.relationship_notes = notes
        if contact_name:
            existing.contact_name = contact_name
        if name:
            existing.name = name
        if cc_emails is not None:
            existing.cc_emails = cc_emails
        return existing

    client = Client(
        workspace_id=workspace_id,
        name=name,
        contact_name=contact_name,
        email=normalized_email,
        cc_emails=cc_emails or [],
        relationship_notes=notes,
    )
    db.add(client)
    db.flush()
    return client


def create_invoice_with_plan(
    db: Session,
    *,
    workspace: Workspace,
    client_id: str | None,
    client: dict[str, Any],
    invoice: dict[str, Any],
    messages: list[dict[str, Any]],
    promise_checkin: dict[str, Any],
    actor: str = "claude",
) -> Invoice:
    invoice_number = str(invoice["invoice_number"]).strip()
    existing = db.scalar(
        select(Invoice).where(
            Invoice.workspace_id == workspace.id,
            Invoice.invoice_number == invoice_number,
        )
    )
    if existing is not None:
        raise DuplicateInvoiceError(_load_invoice(db, existing.id))

    try:
        draft_messages = [
            DraftMessageInput(
                send_on=date.fromisoformat(item["send_on"]),
                tone=item["tone"],
                subject=item["subject"],
                body=item["body"],
            )
            for item in messages
        ]
        checkin = PromiseCheckinInput(
            subject=promise_checkin["subject"],
            body=promise_checkin["body"],
        )
        due_date = date.fromisoformat(invoice["due_date"])
        issue_date = date.fromisoformat(invoice["issue_date"])
        computed = validate_and_compute_messages(
            messages=draft_messages,
            promise_checkin=checkin,
            due_date=due_date,
            workspace=workspace,
        )
    except (KeyError, ValueError) as exc:
        raise PlanValidationError(str(exc)) from exc

    amount_inr = invoice["amount_inr"]
    amount_paise = int(round(float(amount_inr) * 100))
    if amount_paise <= 0:
        raise PlanValidationError("invoice.amount_inr must be > 0")

    db_client = _upsert_client(
        db,
        workspace_id=workspace.id,
        client_id=client_id,
        name=str(client["name"]).strip(),
        contact_name=str(client["contact_name"]).strip(),
        email=str(client["email"]).strip(),
        cc_emails=list(client.get("cc_emails") or []),
        notes=client.get("notes"),
    )

    db_invoice = Invoice(
        workspace_id=workspace.id,
        client_id=db_client.id,
        invoice_number=invoice_number,
        description=invoice.get("description"),
        invoice_url=invoice.get("invoice_url"),
        amount_paise=amount_paise,
        amount_paid_paise=0,
        issue_date=issue_date,
        due_date=due_date,
        status="open",
        plan_status="draft",
        public_token=_public_token(),
    )
    db.add(db_invoice)
    db.flush()

    for item in computed:
        db.add(
            Message(
                invoice_id=db_invoice.id,
                kind=item.kind,
                step=item.step,
                tone=item.tone,
                subject=item.subject,
                body=item.body,
                send_at=item.send_at,
                status="draft",
            )
        )

    _add_event(
        db,
        db_invoice,
        actor=actor,
        event_type="created_by_claude",
        data={"invoice_number": invoice_number},
    )
    db.commit()
    return _load_invoice(db, db_invoice.id)


def approve_plan(db: Session, invoice_id: str, *, actor: str = "owner") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.plan_status != "draft":
        raise EngineError("Only draft plans can be approved")
    if not invoice.workspace.reply_to_email:
        raise EngineError("Set reply-to email in Settings before approving")

    now = now_utc()
    main_messages = [m for m in invoice.messages if m.kind == "main" and m.status == "draft"]
    bump_past_send_ats(main_messages, workspace=invoice.workspace, now=now)
    for message in main_messages:
        message.status = "scheduled"

    invoice.plan_status = "active"
    _add_event(db, invoice, actor=actor, event_type="plan_approved")
    db.commit()
    return _load_invoice(db, invoice_id)


def pause_plan(db: Session, invoice_id: str, *, actor: str = "owner") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.plan_status != "active":
        raise EngineError("Only active plans can be paused")
    _hold_scheduled(invoice.messages)
    invoice.plan_status = "paused"
    _add_event(db, invoice, actor=actor, event_type="plan_paused")
    db.commit()
    return _load_invoice(db, invoice_id)


def resume_plan(db: Session, invoice_id: str, *, actor: str = "owner") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.plan_status != "paused":
        raise EngineError("Only paused plans can be resumed")
    if invoice.status not in {"open", "promised"}:
        raise EngineError("Cannot resume while invoice is waiting on owner confirmation or is closed")

    respace_held_messages(invoice.messages, workspace=invoice.workspace, now=now_utc())
    invoice.plan_status = "active"
    _add_event(db, invoice, actor=actor, event_type="plan_resumed")
    db.commit()
    return _load_invoice(db, invoice_id)


def client_reported_payment(
    db: Session,
    invoice_id: str,
    *,
    amount_paise: int,
    paid_on: date,
    reference: str | None,
    actor: str = "client",
) -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status not in {"open", "promised"}:
        raise EngineError("Payment can only be reported on open or promised invoices")

    invoice.status = "payment_reported"
    invoice.reported_at = now_utc()
    invoice.reported_amount_paise = amount_paise
    invoice.reported_paid_on = paid_on
    invoice.reported_reference = reference
    _hold_scheduled(invoice.messages)
    queue_owner_notice(
        db,
        workspace=invoice.workspace,
        invoice=invoice,
        subject=f"{invoice.client.name} reported payment on {invoice.invoice_number}",
        body=(
            f"{invoice.client.name} reported payment of ₹{amount_paise / 100:,.2f} "
            f"on {paid_on.isoformat()} (ref: {reference or 'n/a'}). Confirm in Tagado."
        ),
    )
    _add_event(
        db,
        invoice,
        actor=actor,
        event_type="payment_reported",
        data={
            "amount_paise": amount_paise,
            "paid_on": paid_on.isoformat(),
            "reference": reference,
        },
    )
    db.commit()
    return _load_invoice(db, invoice_id)


def client_promised(
    db: Session,
    invoice_id: str,
    *,
    promise_date: date,
    actor: str = "client",
) -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status not in {"open", "promised"}:
        raise EngineError("Promise can only be set on open or promised invoices")

    today = today_ist()
    if promise_date < today or promise_date > today + timedelta(days=30):
        raise EngineError("Promise date must be between today and +30 days (IST)")

    invoice.status = "promised"
    invoice.promise_date = promise_date
    invoice.promise_count += 1
    invoice.promise_broken = False

    for message in invoice.messages:
        if message.kind == "main" and message.status == "scheduled":
            message.status = "held"
        if message.kind == "promise_checkin":
            send_at, _ = send_at_for_date(
                promise_date + timedelta(days=1),
                hour_ist=invoice.workspace.send_hour_ist,
                minute_ist=invoice.workspace.send_minute_ist,
            )
            message.send_at = send_at
            message.status = "scheduled"

    queue_owner_notice(
        db,
        workspace=invoice.workspace,
        invoice=invoice,
        subject=f"{invoice.client.name} promised payment on {invoice.invoice_number}",
        body=f"{invoice.client.name} scheduled payment for {promise_date.isoformat()}.",
    )
    _add_event(
        db,
        invoice,
        actor=actor,
        event_type="payment_promised",
        data={"promise_date": promise_date.isoformat(), "promise_count": invoice.promise_count},
    )
    db.commit()
    return _load_invoice(db, invoice_id)


def client_raised_issue(
    db: Session,
    invoice_id: str,
    *,
    kind: str,
    reason: str,
    note: str | None,
    actor: str = "client",
) -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status not in {"open", "promised", "payment_reported"}:
        raise EngineError("Issue cannot be raised on this invoice")
    if kind not in {"need", "problem"}:
        raise EngineError("issue kind must be need or problem")

    invoice.status = "issue_raised"
    invoice.plan_status = "paused"
    invoice.issue_kind = kind
    invoice.issue_reason = reason
    invoice.issue_note = note
    _hold_scheduled(invoice.messages)

    queue_owner_notice(
        db,
        workspace=invoice.workspace,
        invoice=invoice,
        subject=f"Issue raised on {invoice.invoice_number}",
        body=f"{invoice.client.name}: {reason}. {note or ''}".strip(),
    )
    _add_event(
        db,
        invoice,
        actor=actor,
        event_type="issue_raised",
        data={"kind": kind, "reason": reason, "note": note},
    )
    db.commit()
    return _load_invoice(db, invoice_id)


def mark_promise_broken(db: Session, invoice_id: str, *, actor: str = "system") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status != "promised" or invoice.promise_date is None:
        raise EngineError("Invoice is not in a promised state")

    checkin = next((m for m in invoice.messages if m.kind == "promise_checkin"), None)
    if checkin is None or checkin.status != "sent":
        raise EngineError("Promise check-in has not been sent yet")
    if today_ist() <= invoice.promise_date + timedelta(days=3):
        raise EngineError("Promise grace period has not elapsed")

    invoice.status = "open"
    invoice.plan_status = "paused"
    invoice.promise_broken = True
    _add_event(db, invoice, actor=actor, event_type="promise_broken")
    db.commit()
    return _load_invoice(db, invoice_id)


def confirm_payment(
    db: Session,
    invoice_id: str,
    *,
    actor: str = "owner",
    reference: str | None = None,
    note: str | None = None,
) -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status in {"paid", "cancelled"}:
        raise EngineError("Invoice is already closed")

    cancelled = _cancel_unsent(invoice.messages)
    invoice.status = "paid"
    invoice.plan_status = "completed"
    invoice.paid_at = now_utc()
    invoice.amount_paid_paise = invoice.amount_paise
    _add_event(
        db,
        invoice,
        actor=actor,
        event_type="payment_confirmed",
        data={"reference": reference, "note": note, "cancelled_messages": cancelled},
    )
    db.commit()
    return _load_invoice(db, invoice_id)


def reject_payment_report(db: Session, invoice_id: str, *, actor: str = "owner") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status != "payment_reported":
        raise EngineError("No payment report to reject")

    invoice.status = "open"
    invoice.plan_status = "active"
    invoice.reported_at = None
    invoice.reported_amount_paise = None
    invoice.reported_reference = None
    invoice.reported_paid_on = None
    respace_held_messages(invoice.messages, workspace=invoice.workspace, now=now_utc())
    _add_event(db, invoice, actor=actor, event_type="payment_report_rejected")
    db.commit()
    return _load_invoice(db, invoice_id)


def resolve_issue_and_resume(db: Session, invoice_id: str, *, actor: str = "owner") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status != "issue_raised":
        raise EngineError("Invoice has no open issue")

    invoice.status = "open"
    invoice.plan_status = "active"
    invoice.issue_kind = None
    invoice.issue_reason = None
    invoice.issue_note = None
    respace_held_messages(invoice.messages, workspace=invoice.workspace, now=now_utc())
    _add_event(db, invoice, actor=actor, event_type="issue_resolved_resumed")
    db.commit()
    return _load_invoice(db, invoice_id)


def replace_remaining_messages(
    db: Session,
    invoice_id: str,
    *,
    messages: list[dict[str, Any]],
    promise_checkin: dict[str, Any] | None = None,
    actor: str = "claude",
) -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status in {"paid", "cancelled"}:
        raise EngineError("Cannot replace messages on a closed invoice")

    existing_checkin = next((m for m in invoice.messages if m.kind == "promise_checkin"), None)
    checkin_payload = promise_checkin or {
        "subject": existing_checkin.subject if existing_checkin else "Checking in on {{promise_date}}",
        "body": existing_checkin.body
        if existing_checkin
        else "Hi {{contact_name}}, checking whether {{invoice_number}} went out on {{promise_date}}.",
    }

    draft_messages = [
        DraftMessageInput(
            send_on=date.fromisoformat(item["send_on"]),
            tone=item["tone"],
            subject=item["subject"],
            body=item["body"],
        )
        for item in messages
    ]
    computed = validate_and_compute_messages(
        messages=draft_messages,
        promise_checkin=PromiseCheckinInput(
            subject=checkin_payload["subject"],
            body=checkin_payload["body"],
        ),
        due_date=invoice.due_date,
        workspace=invoice.workspace,
    )

    _cancel_unsent(invoice.messages)
    for item in computed:
        db.add(
            Message(
                invoice_id=invoice.id,
                kind=item.kind,
                step=item.step,
                tone=item.tone,
                subject=item.subject,
                body=item.body,
                send_at=item.send_at,
                status="draft",
            )
        )
    invoice.plan_status = "draft"
    _add_event(db, invoice, actor=actor, event_type="messages_replaced")
    db.commit()
    return _load_invoice(db, invoice_id)


def update_message(
    db: Session,
    message_id: str,
    *,
    subject: str | None = None,
    body: str | None = None,
    send_on: date | None = None,
    actor: str = "owner",
) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise EngineError("Message not found")
    invoice = _load_invoice(db, message.invoice_id)

    if invoice.status in {"paid", "cancelled"}:
        raise EngineError("Cannot edit messages on a closed invoice")
    if message.status in {"sent", "cancelled", "sending"}:
        raise EngineError("Message cannot be edited in its current state")

    if actor == "claude":
        if message.status not in UNSENT_STATUSES:
            raise EngineError("Message is not editable")
        invoice.plan_status = "draft"
        for item in invoice.messages:
            if item.status == "scheduled":
                item.status = "draft"
        message.status = "draft"
        event_type = "edited_by_claude"
    else:
        if message.status not in EDITABLE_OWNER_STATUSES:
            raise EngineError("Owner can only edit draft, scheduled, or held messages")
        event_type = "edited_by_owner"

    if subject is not None:
        if len(subject) > 120:
            raise EngineError("subject must be ≤120 characters")
        message.subject = subject.strip()
    if body is not None:
        if len(body) > 1500:
            raise EngineError("body must be ≤1,500 characters")
        message.body = body.strip()
    if send_on is not None and message.kind == "main":
        send_at, _ = send_at_for_date(
            send_on,
            hour_ist=invoice.workspace.send_hour_ist,
            minute_ist=invoice.workspace.send_minute_ist,
        )
        message.send_at = send_at

    _add_event(
        db,
        invoice,
        actor=actor if actor != "claude" else "claude",
        event_type=event_type,
        data={"message_id": message.id},
    )
    db.commit()
    db.refresh(message)
    return message


def cancel_invoice(db: Session, invoice_id: str, *, actor: str = "owner") -> Invoice:
    invoice = _load_invoice(db, invoice_id)
    if invoice.status == "paid":
        raise EngineError("Paid invoices cannot be cancelled")
    if invoice.status == "cancelled":
        return invoice

    _cancel_unsent(invoice.messages)
    invoice.status = "cancelled"
    invoice.plan_status = "cancelled"
    _add_event(db, invoice, actor=actor, event_type="invoice_cancelled")
    db.commit()
    return _load_invoice(db, invoice_id)


def mark_sequence_completed_if_needed(db: Session, invoice_id: str) -> Invoice | None:
    invoice = _load_invoice(db, invoice_id)
    if invoice.plan_status != "active" or invoice.status != "open":
        return None
    mains = [m for m in invoice.messages if m.kind == "main"]
    if not mains:
        return None
    if any(m.status in {"draft", "scheduled", "held", "sending", "failed"} for m in mains):
        return None
    if not all(m.status in {"sent", "cancelled"} for m in mains):
        return None

    invoice.plan_status = "completed"
    _add_event(db, invoice, actor="system", event_type="sequence_completed_unpaid")
    db.commit()
    return _load_invoice(db, invoice_id)


def sunday_shifts(computed: list[ComputedMessage]) -> list[dict[str, str]]:
    return [
        {
            "step": str(item.step),
            "shifted_to": item.sunday_shifted_to.isoformat(),
        }
        for item in computed
        if item.sunday_shifted_to is not None
    ]


def invoice_outstanding_paise(invoice: Invoice) -> int:
    return outstanding_paise(invoice)
