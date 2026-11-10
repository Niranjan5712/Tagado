from __future__ import annotations

from datetime import timedelta

import pytest

from app.services.plans import DraftMessageInput, PlanValidationError, PromiseCheckinInput, validate_and_compute_messages
from app.services.time import today_ist


def test_validate_rejects_unknown_placeholder(workspace):
    today = today_ist()
    with pytest.raises(PlanValidationError, match="unknown placeholders"):
        validate_and_compute_messages(
            messages=[
                DraftMessageInput(
                    send_on=today + timedelta(days=2),
                    tone="friendly",
                    subject="Hello",
                    body="Pay {{wrong_token}} now",
                )
            ],
            promise_checkin=PromiseCheckinInput(
                subject="Check {{promise_date}}",
                body="Body",
            ),
            due_date=today + timedelta(days=20),
            workspace=workspace,
        )


def test_validate_enforces_two_day_gap(workspace):
    today = today_ist()
    with pytest.raises(PlanValidationError, match="at least 2 days"):
        validate_and_compute_messages(
            messages=[
                DraftMessageInput(
                    send_on=today + timedelta(days=2),
                    tone="friendly",
                    subject="One",
                    body="Body one",
                ),
                DraftMessageInput(
                    send_on=today + timedelta(days=3),
                    tone="neutral",
                    subject="Two",
                    body="Body two",
                ),
            ],
            promise_checkin=PromiseCheckinInput(subject="Check {{promise_date}}", body="Body"),
            due_date=today + timedelta(days=20),
            workspace=workspace,
        )


def test_sunday_shifts_to_monday(workspace):
    today = today_ist()
    # Find next Sunday at least 2 days out
    sunday = today + timedelta(days=1)
    while sunday.weekday() != 6:
        sunday += timedelta(days=1)
    if sunday < today + timedelta(days=2):
        sunday += timedelta(days=7)

    computed = validate_and_compute_messages(
        messages=[
            DraftMessageInput(
                send_on=sunday,
                tone="friendly",
                subject="Sunday send",
                body="Body",
            )
        ],
        promise_checkin=PromiseCheckinInput(subject="Check {{promise_date}}", body="Body"),
        due_date=sunday + timedelta(days=30),
        workspace=workspace,
    )
    assert computed[0].sunday_shifted_to is not None
    assert computed[0].sunday_shifted_to.weekday() == 0
