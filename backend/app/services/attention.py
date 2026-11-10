from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Invoice, Message
from app.services.time import now_utc


@dataclass
class AttentionItem:
    type: str
    invoice_id: str
    invoice_number: str
    client_name: str
    summary: str
    owner_options: list[str]
    priority: int
    occurred_at: datetime | None


def get_attention_items(db: Session, workspace_id: str) -> list[AttentionItem]:
    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.workspace_id == workspace_id)
            .options(selectinload(Invoice.client), selectinload(Invoice.messages), selectinload(Invoice.events))
        )
    )
    items: list[AttentionItem] = []

    for invoice in invoices:
        client_name = invoice.client.name if invoice.client else "Client"

        if invoice.status == "issue_raised":
            items.append(
                AttentionItem(
                    type="issue_raised",
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    client_name=client_name,
                    summary=f"{client_name}: '{invoice.issue_reason or 'Issue raised'}'",
                    owner_options=["Resolve and resume in Tagado", "Ask Claude to redraft"],
                    priority=1,
                    occurred_at=_latest_event_time(invoice, "issue_raised"),
                )
            )

        if invoice.status == "payment_reported":
            items.append(
                AttentionItem(
                    type="payment_reported",
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    client_name=client_name,
                    summary=f"{client_name} reported payment — verify in your bank",
                    owner_options=["Confirm payment", "Mark as not received"],
                    priority=2,
                    occurred_at=invoice.reported_at,
                )
            )

        if invoice.promise_broken and invoice.plan_status == "paused":
            items.append(
                AttentionItem(
                    type="promise_broken",
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    client_name=client_name,
                    summary=f"{client_name} missed the promised date",
                    owner_options=["Resume plan", "Ask Claude to redraft"],
                    priority=3,
                    occurred_at=_latest_event_time(invoice, "promise_broken"),
                )
            )

        if invoice.plan_status == "draft" and invoice.status not in {"paid", "cancelled"}:
            items.append(
                AttentionItem(
                    type="plan_awaiting_approval",
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    client_name=client_name,
                    summary="Follow-up plan awaiting your approval",
                    owner_options=["Review and approve in Tagado"],
                    priority=4,
                    occurred_at=invoice.created_at,
                )
            )

        if invoice.plan_status == "completed" and invoice.status == "open":
            items.append(
                AttentionItem(
                    type="sequence_ended_unpaid",
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    client_name=client_name,
                    summary="Follow-up sequence ended and invoice is still unpaid",
                    owner_options=["Ask Claude for next steps", "Add messages"],
                    priority=5,
                    occurred_at=_latest_event_time(invoice, "sequence_completed_unpaid"),
                )
            )

        failed = [m for m in invoice.messages if m.status == "failed"]
        for message in failed:
            items.append(
                AttentionItem(
                    type="send_failed",
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    client_name=client_name,
                    summary=f"Email send failed: {message.error or 'unknown error'}",
                    owner_options=["Check the client email", "Retry send later"],
                    priority=6,
                    occurred_at=message.sent_at or now_utc(),
                )
            )

    items.sort(key=lambda item: (item.priority, item.occurred_at or now_utc()))
    return items


def _latest_event_time(invoice: Invoice, event_type: str) -> datetime | None:
    matched = [event for event in invoice.events if event.type == event_type]
    if not matched:
        return invoice.created_at
    return max(event.created_at for event in matched)
