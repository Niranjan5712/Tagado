from __future__ import annotations

from datetime import timedelta

import pytest

from app.services.engine import (
    DuplicateInvoiceError,
    EngineError,
    approve_plan,
    cancel_invoice,
    client_promised,
    client_raised_issue,
    client_reported_payment,
    confirm_payment,
    create_invoice_with_plan,
    mark_promise_broken,
    mark_sequence_completed_if_needed,
    pause_plan,
    reject_payment_report,
    replace_remaining_messages,
    resolve_issue_and_resume,
    resume_plan,
    update_message,
)
from app.services.stats import compute_client_stats
from app.services.time import today_ist
from tests.helpers import create_and_approve, sample_plan_payload


def test_create_invoice_with_plan_sets_draft_state(db, workspace):
    invoice = create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload())
    assert invoice.status == "open"
    assert invoice.plan_status == "draft"
    assert all(message.status == "draft" for message in invoice.messages)
    checkin = next(m for m in invoice.messages if m.kind == "promise_checkin")
    assert checkin.send_at is None
    assert any(event.type == "created_by_claude" for event in invoice.events)


def test_create_invoice_duplicate_number_errors(db, workspace):
    first = create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload(invoice_number="PX-DUP"))
    with pytest.raises(DuplicateInvoiceError) as exc:
        create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload(invoice_number="PX-DUP"))
    assert exc.value.invoice.id == first.id


def test_approve_plan_schedules_messages(db, workspace):
    invoice = create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload())
    approved = approve_plan(db, invoice.id)
    assert approved.plan_status == "active"
    mains = [m for m in approved.messages if m.kind == "main"]
    assert all(m.status == "scheduled" for m in mains)
    assert all(m.send_at is not None for m in mains)


def test_approve_requires_reply_to(db, workspace):
    workspace.reply_to_email = None
    db.commit()
    invoice = create_invoice_with_plan(db, workspace=workspace, **sample_plan_payload())
    with pytest.raises(EngineError, match="reply-to"):
        approve_plan(db, invoice.id)


def test_pause_and_resume_plan(db, workspace):
    invoice = create_and_approve(db, workspace)
    paused = pause_plan(db, invoice.id)
    assert paused.plan_status == "paused"
    assert all(m.status == "held" for m in paused.messages if m.kind == "main")

    resumed = resume_plan(db, invoice.id)
    assert resumed.plan_status == "active"
    mains = sorted([m for m in resumed.messages if m.kind == "main"], key=lambda m: m.step)
    assert all(m.status == "scheduled" for m in mains)
    assert mains[1].send_at > mains[0].send_at


def test_client_reported_payment_holds_messages(db, workspace):
    invoice = create_and_approve(db, workspace)
    updated = client_reported_payment(
        db,
        invoice.id,
        amount_paise=invoice.amount_paise,
        paid_on=today_ist(),
        reference="UTR123",
    )
    assert updated.status == "payment_reported"
    assert all(m.status != "scheduled" for m in updated.messages if m.kind == "main")


def test_client_promised_schedules_checkin(db, workspace):
    invoice = create_and_approve(db, workspace)
    promise_day = today_ist() + timedelta(days=5)
    updated = client_promised(db, invoice.id, promise_date=promise_day)
    assert updated.status == "promised"
    assert updated.promise_count == 1
    checkin = next(m for m in updated.messages if m.kind == "promise_checkin")
    assert checkin.status == "scheduled"
    assert checkin.send_at is not None
    assert all(m.status == "held" for m in updated.messages if m.kind == "main")


def test_client_raised_issue_pauses_plan(db, workspace):
    invoice = create_and_approve(db, workspace)
    updated = client_raised_issue(
        db,
        invoice.id,
        kind="need",
        reason="PO number missing",
        note="Please add PO PO-441",
    )
    assert updated.status == "issue_raised"
    assert updated.plan_status == "paused"


def test_mark_promise_broken(db, workspace):
    invoice = create_and_approve(db, workspace)
    promise_day = today_ist() - timedelta(days=5)
    updated = client_promised(db, invoice.id, promise_date=today_ist() + timedelta(days=1))
    # Force past promise + sent check-in for cron path
    updated.promise_date = promise_day
    checkin = next(m for m in updated.messages if m.kind == "promise_checkin")
    checkin.status = "sent"
    db.commit()

    broken = mark_promise_broken(db, invoice.id)
    assert broken.status == "open"
    assert broken.plan_status == "paused"
    assert broken.promise_broken is True


def test_confirm_payment_cancels_unsent(db, workspace):
    invoice = create_and_approve(db, workspace)
    paid = confirm_payment(db, invoice.id, reference="NEFT-99")
    assert paid.status == "paid"
    assert paid.plan_status == "completed"
    assert all(m.status in {"sent", "cancelled"} for m in paid.messages)


def test_reject_payment_report_resumes(db, workspace):
    invoice = create_and_approve(db, workspace)
    client_reported_payment(
        db,
        invoice.id,
        amount_paise=invoice.amount_paise,
        paid_on=today_ist(),
        reference="UTR",
    )
    rejected = reject_payment_report(db, invoice.id)
    assert rejected.status == "open"
    assert rejected.plan_status == "active"
    assert any(m.status == "scheduled" for m in rejected.messages if m.kind == "main")


def test_resolve_issue_and_resume(db, workspace):
    invoice = create_and_approve(db, workspace)
    client_raised_issue(db, invoice.id, kind="need", reason="GSTIN correction", note=None)
    resolved = resolve_issue_and_resume(db, invoice.id)
    assert resolved.status == "open"
    assert resolved.plan_status == "active"
    assert resolved.issue_reason is None


def test_replace_remaining_messages_returns_to_draft(db, workspace):
    invoice = create_and_approve(db, workspace)
    today = today_ist()
    replaced = replace_remaining_messages(
        db,
        invoice.id,
        messages=[
            {
                "send_on": (today + timedelta(days=2)).isoformat(),
                "tone": "firm",
                "subject": "Revised note on {{invoice_number}}",
                "body": "Hi {{contact_name}}, revised follow-up for {{outstanding}}.",
            },
            {
                "send_on": (today + timedelta(days=5)).isoformat(),
                "tone": "firm",
                "subject": "Second note",
                "body": "Please share a date.",
            },
        ],
    )
    assert replaced.plan_status == "draft"
    assert any(m.status == "cancelled" for m in replaced.messages)
    assert any(m.status == "draft" and "Revised" in m.subject for m in replaced.messages)


def test_update_message_by_claude_forces_draft(db, workspace):
    from app.services.engine import _load_invoice

    invoice = create_and_approve(db, workspace)
    message = next(m for m in invoice.messages if m.kind == "main")
    update_message(db, message.id, body="Softer wording for {{contact_name}}.", actor="claude")
    loaded = _load_invoice(db, invoice.id)
    refreshed = next(m for m in loaded.messages if m.id == message.id)
    assert loaded.plan_status == "draft"
    assert refreshed.status == "draft"


def test_update_message_by_owner_keeps_plan(db, workspace):
    from app.services.engine import _load_invoice

    invoice = create_and_approve(db, workspace)
    message = next(m for m in invoice.messages if m.kind == "main")
    update_message(db, message.id, subject="Tweaked subject", actor="owner")
    refreshed = _load_invoice(db, invoice.id)
    assert refreshed.plan_status == "active"
    assert next(m for m in refreshed.messages if m.id == message.id).subject == "Tweaked subject"


def test_cancel_invoice(db, workspace):
    invoice = create_and_approve(db, workspace)
    cancelled = cancel_invoice(db, invoice.id)
    assert cancelled.status == "cancelled"
    assert cancelled.plan_status == "cancelled"


def test_sequence_completed_when_mains_sent(db, workspace):
    invoice = create_and_approve(db, workspace)
    for message in invoice.messages:
        if message.kind == "main":
            message.status = "sent"
    db.commit()
    completed = mark_sequence_completed_if_needed(db, invoice.id)
    assert completed is not None
    assert completed.plan_status == "completed"


def test_client_stats_for_seed_like_history(db, workspace):
    warm = create_invoice_with_plan(
        db,
        workspace=workspace,
        **sample_plan_payload(
            invoice_number="PX-W1",
            client_name="Kalpataru Retail Pvt Ltd",
            email="rahul.mehta@kalpataru-retail.example",
        ),
    )
    confirm_payment(db, warm.id)
    stats = compute_client_stats(db, warm.client_id)
    assert stats.paid_count == 1
    assert stats.invoices_total == 1
