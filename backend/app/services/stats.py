from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Client, Invoice
from app.services.plans import outstanding_paise
from app.services.time import ensure_utc, today_ist


@dataclass
class ClientStats:
    invoices_total: int
    paid_count: int
    on_time_pct: float
    avg_days_late: float
    broken_promises: int
    open_issues: int
    outstanding: int


def compute_client_stats(db: Session, client_id: str, *, today: date | None = None) -> ClientStats:
    today_value = today or today_ist()
    invoices = list(db.scalars(select(Invoice).where(Invoice.client_id == client_id)))
    paid = [inv for inv in invoices if inv.status == "paid" and inv.paid_at is not None]
    on_time = 0
    late_days: list[int] = []
    for inv in paid:
        paid_at = ensure_utc(inv.paid_at)
        paid_day = paid_at.date() if paid_at else today_value
        delta = (paid_day - inv.due_date).days
        if delta <= 0:
            on_time += 1
            late_days.append(0)
        else:
            late_days.append(delta)

    paid_count = len(paid)
    outstanding = sum(outstanding_paise(inv) for inv in invoices if inv.status != "cancelled")
    open_issues = sum(1 for inv in invoices if inv.status == "issue_raised")
    broken = sum(1 for inv in invoices if inv.promise_broken)

    return ClientStats(
        invoices_total=len(invoices),
        paid_count=paid_count,
        on_time_pct=round((on_time / paid_count) * 100, 1) if paid_count else 0.0,
        avg_days_late=round(sum(late_days) / len(late_days), 1) if late_days else 0.0,
        broken_promises=broken,
        open_issues=open_issues,
        outstanding=outstanding,
    )


def workspace_dashboard_totals(db: Session, workspace_id: str, *, today: date | None = None) -> dict:
    today_value = today or today_ist()
    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.workspace_id == workspace_id)
            .options(selectinload(Invoice.messages))
        )
    )

    openish = [inv for inv in invoices if inv.status in {"open", "promised", "payment_reported", "issue_raised"}]
    outstanding_paise_total = sum(outstanding_paise(inv) for inv in openish)
    overdue = [
        inv
        for inv in invoices
        if inv.status in {"open", "promised"} and inv.due_date < today_value
    ]
    overdue_paise = sum(outstanding_paise(inv) for inv in overdue)

    collected = 0
    for inv in invoices:
        if inv.status == "paid" and inv.paid_at is not None:
            paid_at = ensure_utc(inv.paid_at)
            assert paid_at is not None
            age_days = (today_value - paid_at.date()).days
            if age_days <= 30:
                collected += inv.amount_paid_paise

    week_end = today_value + timedelta(days=7)
    due_soon = [
        inv
        for inv in invoices
        if inv.status in {"open", "promised"}
        and today_value <= inv.due_date <= week_end
    ]
    promised = [inv for inv in invoices if inv.status == "promised"]
    open_issues = [inv for inv in invoices if inv.status == "issue_raised"]
    payment_reported = [inv for inv in invoices if inv.status == "payment_reported"]
    awaiting_approval = [
        inv
        for inv in invoices
        if inv.plan_status == "draft" and inv.status not in {"paid", "cancelled"}
    ]
    held_reminders = [
        inv
        for inv in invoices
        if inv.status in {"open", "promised", "payment_reported", "issue_raised"}
        and any(m.status == "held" for m in (inv.messages or []))
    ]

    return {
        "outstanding_paise": outstanding_paise_total,
        "outstanding_count": len(openish),
        "overdue_paise": overdue_paise,
        "overdue_count": len(overdue),
        "collected_30d_paise": collected,
        "due_soon_paise": sum(outstanding_paise(inv) for inv in due_soon),
        "due_soon_count": len(due_soon),
        "promised_paise": sum(outstanding_paise(inv) for inv in promised),
        "promised_count": len(promised),
        "open_issues_count": len(open_issues),
        "payment_reported_count": len(payment_reported),
        "awaiting_approval_count": len(awaiting_approval),
        "held_reminders_count": len(held_reminders),
    }


def find_clients_by_query(db: Session, workspace_id: str, query: str, *, limit: int = 3) -> list[Client]:
    needle = query.strip().lower()
    clients = list(db.scalars(select(Client).where(Client.workspace_id == workspace_id)))
    if not needle:
        return clients[:limit]
    scored: list[tuple[int, Client]] = []
    for client in clients:
        hay = f"{client.name} {client.email} {client.contact_name}".lower()
        if needle in hay:
            scored.append((0 if hay.startswith(needle) else 1, client))
    scored.sort(key=lambda item: (item[0], item[1].name))
    return [client for _, client in scored[:limit]]
