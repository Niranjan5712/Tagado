from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.session import SessionLocal
from app.main import create_app
from app.services.engine import approve_plan, create_invoice_with_plan
from app.services.time import now_utc
from tests.helpers import sample_plan_payload


def test_cron_tick_requires_secret_and_sends(db, workspace):
    # Re-bind app to use same engine/sessionmaker as the test fixture
    settings = get_settings()
    invoice = create_invoice_with_plan(
        db,
        workspace=workspace,
        **sample_plan_payload(invoice_number="PX-CRON1"),
    )
    approved = approve_plan(db, invoice.id)
    message = next(m for m in approved.messages if m.kind == "main" and m.step == 1)
    message.send_at = now_utc() - timedelta(minutes=1)
    db.commit()

    app = create_app()
    client = TestClient(app)

    unauthorized = client.post("/api/cron/tick")
    assert unauthorized.status_code == 401

    ok = client.post("/api/cron/tick", headers={"x-cron-secret": settings.cron_secret})
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["sent"] >= 1
