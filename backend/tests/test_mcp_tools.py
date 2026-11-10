from __future__ import annotations

from datetime import timedelta

from app.mcp.context import current_workspace_id, current_workspace_name
from app.mcp.schemas import ClientPayload, InvoicePayload, MessagePayload, PromiseCheckinPayload
from app.mcp.tools import (
    create_invoice_with_plan_tool,
    get_attention_items_tool,
    get_client_context,
    get_invoice_tool,
    list_invoices_tool,
    ping,
)
from app.services.time import today_ist
from app.config import get_settings


def _set_workspace(workspace) -> None:
    current_workspace_id.set(workspace.id)
    current_workspace_name.set(workspace.business_name)


def test_ping_and_list_seeded_workspace(db, workspace):
    _set_workspace(workspace)
    # Attach seed clients/invoices onto the fixture workspace
    settings = get_settings()
    from app.services.seed import seed_demo_business_data

    seed_demo_business_data(db, workspace, settings)
    db.commit()

    result = ping()
    assert result["workspace_name"] == workspace.business_name

    listed = list_invoices_tool()
    assert listed["totals"]["outstanding_count"] >= 1

    attention = get_attention_items_tool()
    assert isinstance(attention["items"], list)


def test_get_client_context_found_and_new(db, workspace):
    settings = get_settings()
    from app.services.seed import seed_demo_business_data

    seed_demo_business_data(db, workspace, settings)
    db.commit()
    _set_workspace(workspace)

    found = get_client_context("Kalpataru")
    assert found["found"] is True
    assert found["matches"][0]["name"] == "Kalpataru Retail Pvt Ltd"

    missing = get_client_context("Brand new studio that does not exist")
    assert missing["found"] is False
    assert "create_invoice_with_plan will create them" in missing["summary"]


def test_create_invoice_onboards_new_client(db, workspace):
    _set_workspace(workspace)
    today = today_ist()
    created = create_invoice_with_plan_tool(
        client=ClientPayload(
            name="Sagarika Interiors",
            contact_name="Meera Nair",
            email="meera.nair@sagarika-interiors.example",
            cc_emails=["accounts@sagarika-interiors.example"],
            notes="New boutique client in Kochi.",
        ),
        invoice=InvoicePayload(
            invoice_number="PX-4501",
            amount_inr=75000,
            issue_date=today.isoformat(),
            due_date=(today + timedelta(days=18)).isoformat(),
            description="Showroom moodboards",
        ),
        messages=[
            MessagePayload(
                send_on=(today + timedelta(days=2)).isoformat(),
                tone="friendly",
                subject="Note on {{invoice_number}}",
                body="Hi {{contact_name}}, {{invoice_number}} for {{amount}} is due {{due_date}}.",
            ),
            MessagePayload(
                send_on=(today + timedelta(days=5)).isoformat(),
                tone="neutral",
                subject="Following up on {{invoice_number}}",
                body="Hi {{contact_name}}, checking if {{invoice_number}} is in your payment run.",
            ),
            MessagePayload(
                send_on=(today + timedelta(days=9)).isoformat(),
                tone="firm",
                subject="Need a date for {{invoice_number}}",
                body="Hi {{contact_name}}, please share a date for {{outstanding}}.",
            ),
        ],
        promise_checkin=PromiseCheckinPayload(
            subject="Checking {{promise_date}}",
            body="Hi {{contact_name}}, checking whether {{invoice_number}} went out on {{promise_date}}.",
        ),
        client_id=None,
    )

    assert created["already_tracked"] is False
    assert created["plan_status"] == "draft"
    assert "review_url" in created

    ctx = get_client_context("Sagarika")
    assert ctx["found"] is True
    assert ctx["matches"][0]["email"] == "meera.nair@sagarika-interiors.example"

    detail = get_invoice_tool(invoice_number="PX-4501")
    assert detail["invoice"]["invoice_number"] == "PX-4501"
    assert detail["client"]["name"] == "Sagarika Interiors"


def test_duplicate_create_is_safe(db, workspace):
    _set_workspace(workspace)
    today = today_ist()
    payload = dict(
        client=ClientPayload(
            name="Sagarika Interiors",
            contact_name="Meera Nair",
            email="meera.nair@sagarika-interiors.example",
        ),
        invoice=InvoicePayload(
            invoice_number="PX-4502",
            amount_inr=50000,
            issue_date=today.isoformat(),
            due_date=(today + timedelta(days=15)).isoformat(),
        ),
        messages=[
            MessagePayload(
                send_on=(today + timedelta(days=2)).isoformat(),
                tone="friendly",
                subject="{{invoice_number}}",
                body="Hi {{contact_name}}",
            ),
            MessagePayload(
                send_on=(today + timedelta(days=5)).isoformat(),
                tone="neutral",
                subject="Follow up {{invoice_number}}",
                body="Hello {{contact_name}}",
            ),
        ],
        promise_checkin=PromiseCheckinPayload(
            subject="Check {{promise_date}}",
            body="Hi {{contact_name}} on {{promise_date}}",
        ),
    )
    first = create_invoice_with_plan_tool(**payload)
    second = create_invoice_with_plan_tool(**payload)
    assert first["invoice_id"] == second["invoice_id"]
    assert second["already_tracked"] is True
