from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_workspace
from app.db.models import Invoice, Workspace
from app.db.session import get_db
from app.services.attention import get_attention_items
from app.services.money import format_inr_display, paise_to_inr
from app.services.serialize import serialize_invoice_summary
from app.services.stats import workspace_dashboard_totals

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
) -> dict:
    totals = workspace_dashboard_totals(db, workspace.id)
    attention = get_attention_items(db, workspace.id)
    invoices = list(
        db.scalars(
            select(Invoice)
            .where(Invoice.workspace_id == workspace.id)
            .options(selectinload(Invoice.client), selectinload(Invoice.messages))
            .order_by(Invoice.due_date.asc())
        )
    )
    return {
        "totals": {
            "outstanding_display": format_inr_display(totals["outstanding_paise"]),
            "outstanding_inr": paise_to_inr(totals["outstanding_paise"]),
            "outstanding_count": totals["outstanding_count"],
            "overdue_display": format_inr_display(totals["overdue_paise"]),
            "overdue_inr": paise_to_inr(totals["overdue_paise"]),
            "overdue_count": totals["overdue_count"],
            "needs_attention_count": len(attention),
            "collected_30d_display": format_inr_display(totals["collected_30d_paise"]),
            "collected_30d_inr": paise_to_inr(totals["collected_30d_paise"]),
        },
        "attention": [
            {
                "type": item.type,
                "invoice_id": item.invoice_id,
                "invoice_number": item.invoice_number,
                "client_name": item.client_name,
                "summary": item.summary,
                "owner_options": item.owner_options,
                "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
            }
            for item in attention
        ],
        "invoices": [serialize_invoice_summary(invoice) for invoice in invoices],
    }
