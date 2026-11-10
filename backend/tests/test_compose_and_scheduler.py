from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.config import get_settings
from app.db.models import OutboundEmail
from app.services.email.compose import compose_message_email
from app.services.engine import approve_plan, create_invoice_with_plan
from app.services.scheduler import SendError, claim_due_messages, send_one_now, tick
from app.services.time import now_utc
from tests.helpers import sample_plan_payload


def _approved_invoice(db, workspace):
    invoice = create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload(invoice_number="PX-S001"))
    return approve_plan(db, invoice.id)


def test_compose_fills_placeholders_and_footer(db, workspace):
    invoice = _approved_invoice(db, workspace)
    message = next(m for m in invoice.messages if m.kind == "main")
    message.include_msme_note = True
    db.commit()

    composed = compose_message_email(
        invoice=invoice,
        message=message,
        workspace=workspace,
        settings=get_settings(),
    )
    assert "Rahul Mehta" in composed.subject or "PX-S001" in composed.subject or "{{" not in composed.subject
    assert "{{" not in composed.html
    assert "/p/" in composed.html
    assert "View invoice and respond" in composed.html
    assert workspace.udyam_number in composed.html
    assert "MSMED Act" in composed.text
    assert composed.to_addrs == ["rahul.mehta@kalpataru-retail.example"]


def test_send_now_writes_outbox_and_marks_sent(db, workspace):
    invoice = _approved_invoice(db, workspace)
    message = next(m for m in invoice.messages if m.kind == "main" and m.step == 1)

    result = send_one_now(db, message.id, settings=get_settings())
    assert result["status"] == "sent"

    db.refresh(message)
    assert message.status == "sent"
    assert message.sent_to is not None

    outbox = db.get(OutboundEmail, result["outbound_email_id"])
    assert outbox is not None
    assert outbox.kind == "reminder"
    assert "/p/" in outbox.html
    assert invoice.public_token in outbox.html


def test_send_now_rejects_draft_plan(db, workspace):
    invoice = create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload(invoice_number="PX-S002"))
    message = next(m for m in invoice.messages if m.kind == "main")
    try:
        send_one_now(db, message.id)
        raise AssertionError("expected SendError")
    except SendError as exc:
        assert "Approve the plan first" in str(exc)


def test_cron_tick_sends_due_message_once(db, workspace):
    invoice = _approved_invoice(db, workspace)
    message = next(m for m in invoice.messages if m.kind == "main" and m.step == 1)
    message.send_at = now_utc() - timedelta(minutes=1)
    db.commit()

    first = tick(db, settings=get_settings())
    assert first["claimed"] == 1
    assert first["sent"] == 1

    second = tick(db, settings=get_settings())
    assert second["claimed"] == 0
    assert second["sent"] == 0

    rows = list(
        db.scalars(
            select(OutboundEmail).where(
                OutboundEmail.message_id == message.id,
                OutboundEmail.kind == "reminder",
            )
        )
    )
    assert len(rows) == 1


def test_parallel_claims_do_not_double_send(db, workspace):
    invoice = _approved_invoice(db, workspace)
    message = next(m for m in invoice.messages if m.kind == "main" and m.step == 1)
    message.send_at = now_utc() - timedelta(minutes=2)
    db.commit()

    claimed_a = claim_due_messages(db)
    claimed_b = claim_due_messages(db)
    assert len(claimed_a) == 1
    assert claimed_a[0].id == message.id
    assert claimed_b == []
