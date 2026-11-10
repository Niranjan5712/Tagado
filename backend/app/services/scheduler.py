from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.db.models import Event, Invoice, Message
from app.services.email.compose import compose_message_email
from app.services.email.send import send_email
from app.services.engine import mark_promise_broken, mark_sequence_completed_if_needed
from app.services.time import ensure_utc, now_utc, today_ist


class SendError(ValueError):
    pass


def claim_due_messages(db: Session, *, limit: int = 20) -> list[Message]:
    """Atomically claim due scheduled messages for sending (SQLite-safe)."""
    now = now_utc()
    candidate_ids = list(
        db.scalars(
            select(Message.id)
            .join(Invoice, Invoice.id == Message.invoice_id)
            .where(
                Message.status == "scheduled",
                Message.send_at.is_not(None),
                Message.send_at <= now,
                Invoice.plan_status == "active",
                Invoice.status.in_(("open", "promised")),
            )
            .order_by(Message.send_at.asc())
            .limit(limit)
        )
    )

    claimed_ids: list[str] = []
    claim_time = now_utc()
    for message_id in candidate_ids:
        result = db.execute(
            update(Message)
            .where(Message.id == message_id, Message.status == "scheduled")
            .values(
                status="sending",
                attempts=Message.attempts + 1,
                sent_at=claim_time,  # claim timestamp until send completes/fails
            )
        )
        if result.rowcount == 1:
            claimed_ids.append(message_id)

    db.flush()
    if not claimed_ids:
        return []

    return list(
        db.scalars(
            select(Message)
            .where(Message.id.in_(claimed_ids))
            .options(
                selectinload(Message.invoice).selectinload(Invoice.client),
                selectinload(Message.invoice).selectinload(Invoice.workspace),
            )
        )
    )


def claim_message_for_send_now(db: Session, message_id: str) -> Message:
    message = db.scalar(
        select(Message)
        .where(Message.id == message_id)
        .options(
            selectinload(Message.invoice).selectinload(Invoice.client),
            selectinload(Message.invoice).selectinload(Invoice.workspace),
        )
    )
    if message is None:
        raise SendError("Message not found")

    invoice = message.invoice
    if invoice.plan_status != "active":
        raise SendError("Approve the plan first")
    if invoice.status not in {"open", "promised"}:
        raise SendError("Invoice is not in a sendable state")
    if message.status not in {"scheduled", "held"}:
        if message.status == "sending":
            raise SendError("Being sent right now")
        raise SendError(f"Message cannot be sent from status '{message.status}'")

    claim_time = now_utc()
    result = db.execute(
        update(Message)
        .where(
            Message.id == message_id,
            Message.status.in_(("scheduled", "held")),
        )
        .values(
            status="sending",
            attempts=Message.attempts + 1,
            sent_at=claim_time,
        )
    )
    if result.rowcount != 1:
        raise SendError("Could not claim message for sending")
    db.flush()
    db.refresh(message)
    return message


def deliver_claimed_message(
    db: Session,
    message: Message,
    *,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    invoice = message.invoice
    workspace = invoice.workspace

    try:
        composed = compose_message_email(
            invoice=invoice,
            message=message,
            workspace=workspace,
            settings=settings,
        )
        result = send_email(
            db,
            workspace_id=workspace.id,
            invoice_id=invoice.id,
            message_id=message.id,
            to_addrs=composed.to_addrs,
            cc_addrs=composed.cc_addrs,
            reply_to=composed.reply_to,
            subject=composed.subject,
            html=composed.html,
            text=composed.text,
            kind="reminder",
        )
    except Exception as exc:  # noqa: BLE001 — convert to failed/retry path
        _mark_send_failure(db, message, error=str(exc))
        db.commit()
        return {
            "message_id": message.id,
            "status": message.status,
            "error": str(exc),
        }

    message.status = "sent"
    message.sent_at = now_utc()
    message.sent_to = ", ".join(result.to_addrs)
    message.error = None
    db.add(
        Event(
            invoice_id=invoice.id,
            actor="system",
            type="message_sent",
            data={
                "message_id": message.id,
                "to": result.to_addrs,
                "outbound_email_id": result.outbound_email_id,
                "subject": result.subject,
            },
        )
    )
    db.commit()
    return {
        "message_id": message.id,
        "status": "sent",
        "outbound_email_id": result.outbound_email_id,
        "to": result.to_addrs,
        "client_page_url": composed.client_page_url,
    }


def send_one_now(
    db: Session,
    message_id: str,
    *,
    settings: Settings | None = None,
) -> dict:
    message = claim_message_for_send_now(db, message_id)
    return deliver_claimed_message(db, message, settings=settings)


def recover_stuck_sending(db: Session, *, older_than_minutes: int = 10) -> int:
    """Fail messages stuck in sending longer than the grace window (claim time stored in sent_at)."""
    cutoff = now_utc() - timedelta(minutes=older_than_minutes)
    stuck = list(db.scalars(select(Message).where(Message.status == "sending")))
    count = 0
    for message in stuck:
        claimed_at = ensure_utc(message.sent_at)
        if claimed_at is None or claimed_at > cutoff:
            continue
        message.status = "failed"
        message.error = message.error or "Stuck in sending state"
        message.sent_at = None
        count += 1
    if count:
        db.commit()
    return count


def _mark_send_failure(db: Session, message: Message, *, error: str) -> None:
    if message.attempts < 3:
        message.status = "scheduled"
        message.error = error
        message.sent_at = None
    else:
        message.status = "failed"
        message.error = error
        message.sent_at = None
        db.add(
            Event(
                invoice_id=message.invoice_id,
                actor="system",
                type="message_send_failed",
                data={"message_id": message.id, "error": error},
            )
        )


def run_promise_checks(db: Session) -> int:
    today = today_ist()
    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.status == "promised", Invoice.promise_date.is_not(None))
            .options(selectinload(Invoice.messages))
        )
    )
    broken = 0
    for invoice in invoices:
        assert invoice.promise_date is not None
        if today <= invoice.promise_date + timedelta(days=3):
            continue
        checkin = next((m for m in invoice.messages if m.kind == "promise_checkin"), None)
        if checkin is None or checkin.status != "sent":
            continue
        try:
            mark_promise_broken(db, invoice.id)
            broken += 1
        except Exception:  # noqa: BLE001
            db.rollback()
    return broken


def run_sequence_completion_checks(db: Session) -> int:
    invoice_ids = list(
        db.scalars(
            select(Invoice.id).where(
                Invoice.plan_status == "active",
                Invoice.status == "open",
            )
        )
    )
    completed = 0
    for invoice_id in invoice_ids:
        result = mark_sequence_completed_if_needed(db, invoice_id)
        if result is not None:
            completed += 1
    return completed


def tick(db: Session, *, settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    recovered = recover_stuck_sending(db)
    claimed = claim_due_messages(db)
    sent = 0
    failed = 0
    results = []
    for message in claimed:
        outcome = deliver_claimed_message(db, message, settings=settings)
        results.append(outcome)
        if outcome.get("status") == "sent":
            sent += 1
        else:
            failed += 1

    broken = run_promise_checks(db)
    completed = run_sequence_completion_checks(db)
    return {
        "claimed": len(claimed),
        "sent": sent,
        "failed": failed,
        "recovered_stuck": recovered,
        "promises_broken": broken,
        "sequences_completed": completed,
        "results": results,
    }
