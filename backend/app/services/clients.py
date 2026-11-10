from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Client, Invoice
from app.services.money import format_inr, paise_to_inr
from app.services.stats import compute_client_stats, find_clients_by_query
from app.services.time import ensure_utc, format_today_ist, today_ist


def get_context(db: Session, workspace_id: str, query: str) -> dict:
    matches = find_clients_by_query(db, workspace_id, query, limit=3)
    today = format_today_ist()
    if not matches:
        return {
            "today_ist": today,
            "found": False,
            "matches": [],
            "summary": (
                "New client; create_invoice_with_plan will create them when you pass "
                "client name, contact_name, and email."
            ),
        }

    payload = []
    for client in matches:
        stats = compute_client_stats(db, client.id)
        invoices = list(
            db.scalars(
                select(Invoice)
                .where(Invoice.client_id == client.id)
                .order_by(Invoice.due_date.desc())
                .limit(5)
            )
        )
        payload.append(
            {
                "client_id": client.id,
                "name": client.name,
                "contact_name": client.contact_name,
                "email": client.email,
                "cc_emails": client.cc_emails or [],
                "relationship_notes": client.relationship_notes,
                "stats": {
                    "invoices_total": stats.invoices_total,
                    "paid_count": stats.paid_count,
                    "on_time_pct": stats.on_time_pct,
                    "avg_days_late": stats.avg_days_late,
                    "broken_promises": stats.broken_promises,
                    "open_issues": stats.open_issues,
                    "outstanding_inr": paise_to_inr(stats.outstanding),
                    "outstanding_display": format_inr(stats.outstanding),
                },
                "recent_invoices": [_invoice_history_row(inv) for inv in invoices],
            }
        )

    return {
        "today_ist": today,
        "found": True,
        "matches": payload,
        "summary": f"Found {len(payload)} client match(es) for '{query}'.",
    }


def _invoice_history_row(invoice: Invoice) -> dict:
    paid_at = ensure_utc(invoice.paid_at)
    paid_date = paid_at.date().isoformat() if paid_at else None
    days_late = None
    if paid_at is not None:
        days_late = max((paid_at.date() - invoice.due_date).days, 0)
    return {
        "invoice_number": invoice.invoice_number,
        "amount_inr": paise_to_inr(invoice.amount_paise),
        "due_date": invoice.due_date.isoformat(),
        "paid_date": paid_date,
        "days_late": days_late,
        "status": invoice.status,
    }
