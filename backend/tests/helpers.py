from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from app.db.models import Invoice, Workspace
from app.services.engine import approve_plan, create_invoice_with_plan
from app.services.time import today_ist


def sample_plan_payload(
    *,
    invoice_number: str = "PX-9001",
    client_name: str = "Kalpataru Retail Pvt Ltd",
    contact_name: str = "Rahul Mehta",
    email: str = "rahul.mehta@kalpataru-retail.example",
    amount_inr: float = 180000,
    days_to_due: int = 20,
):
    today = today_ist()
    due = today + timedelta(days=days_to_due)
    return {
        "client_id": None,
        "client": {
            "name": client_name,
            "contact_name": contact_name,
            "email": email,
            "cc_emails": ["accounts@kalpataru-retail.example"],
            "notes": "Keep it warm.",
        },
        "invoice": {
            "invoice_number": invoice_number,
            "amount_inr": amount_inr,
            "issue_date": today.isoformat(),
            "due_date": due.isoformat(),
            "description": "Brand work",
        },
        "messages": [
            {
                "send_on": (today + timedelta(days=2)).isoformat(),
                "tone": "friendly",
                "subject": "Heads-up on {{invoice_number}}",
                "body": "Hi {{contact_name}}, {{invoice_number}} for {{amount}} falls due on {{due_date}}.",
            },
            {
                "send_on": (today + timedelta(days=5)).isoformat(),
                "tone": "neutral",
                "subject": "Following up on {{invoice_number}}",
                "body": "Hi {{contact_name}}, checking if {{invoice_number}} is in your next payment run.",
            },
            {
                "send_on": (today + timedelta(days=10)).isoformat(),
                "tone": "firm",
                "subject": "Need a payment date for {{invoice_number}}",
                "body": "Hi {{contact_name}}, please share a committed date for {{outstanding}}.",
            },
        ],
        "promise_checkin": {
            "subject": "Checking in on {{promise_date}}",
            "body": "Hi {{contact_name}}, checking whether {{invoice_number}} went out on {{promise_date}}.",
        },
    }


def create_and_approve(db: Session, workspace: Workspace, **overrides) -> Invoice:
    payload = sample_plan_payload(**overrides)
    invoice = create_invoice_with_plan(db, workspace=workspace, **payload)
    return approve_plan(db, invoice.id)
