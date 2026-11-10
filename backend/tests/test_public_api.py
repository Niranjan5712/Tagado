from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.engine import approve_plan, create_invoice_with_plan
from app.services.time import today_ist
from tests.helpers import sample_plan_payload


def test_public_page_flow_need_promise_and_paid(db, workspace):
    invoice = create_invoice_with_plan(
        db,
        workspace=workspace,
        **sample_plan_payload(invoice_number="PX-PUB1", amount_inr=75000),
    )
    approved = approve_plan(db, invoice.id)
    token = approved.public_token

    app = create_app()
    client = TestClient(app)

    missing = client.get("/api/public/invoices/not-a-real-token-value-xxxxxx")
    assert missing.status_code == 404

    page = client.get(f"/api/public/invoices/{token}")
    assert page.status_code == 200
    body = page.json()
    assert body["invoice_number"] == "PX-PUB1"
    assert "client" not in body
    assert "messages" not in body
    assert body["can_respond"] is True
    assert body["bank"]["ifsc"] == workspace.ifsc
    assert body["upi_available"] is True

    qr = client.get(f"/api/public/invoices/{token}/upi-qr.png")
    assert qr.status_code == 200
    assert qr.headers["content-type"] == "image/png"

    # Over ₹1 lakh: UPI QR must not be offered
    large = create_invoice_with_plan(
        db,
        workspace=workspace,
        **sample_plan_payload(invoice_number="PX-PUB0", amount_inr=180000, email="large@kalpataru-retail.example"),
    )
    large_approved = approve_plan(db, large.id)
    large_page = client.get(f"/api/public/invoices/{large_approved.public_token}")
    assert large_page.json()["upi_available"] is False
    assert client.get(f"/api/public/invoices/{large_approved.public_token}/upi-qr.png").status_code == 404

    need = client.post(
        f"/api/public/invoices/{token}/respond",
        json={"type": "need", "reason": "PO number missing", "note": "Please add PO"},
    )
    assert need.status_code == 200
    assert need.json()["status"] == "issue_raised"
    assert need.json()["can_respond"] is False

    # Resolve path is owner-side; create a fresh invoice for promise + paid
    invoice2 = create_invoice_with_plan(
        db,
        workspace=workspace,
        **sample_plan_payload(
            invoice_number="PX-PUB2",
            email="accounts@kalpataru-retail.example",
        ),
    )
    approved2 = approve_plan(db, invoice2.id)
    token2 = approved2.public_token

    promise_day = (today_ist() + timedelta(days=5)).isoformat()
    scheduled = client.post(
        f"/api/public/invoices/{token2}/respond",
        json={"type": "scheduled", "promise_date": promise_day},
    )
    assert scheduled.status_code == 200
    assert scheduled.json()["status"] == "promised"

    invoice3 = create_invoice_with_plan(
        db,
        workspace=workspace,
        **sample_plan_payload(
            invoice_number="PX-PUB3",
            email="finance@kalpataru-retail.example",
        ),
    )
    approved3 = approve_plan(db, invoice3.id)
    token3 = approved3.public_token
    paid = client.post(
        f"/api/public/invoices/{token3}/respond",
        json={
            "type": "paid",
            "amount_inr": 180000,
            "paid_on": today_ist().isoformat(),
            "reference": "UTR123456",
        },
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "payment_reported"
