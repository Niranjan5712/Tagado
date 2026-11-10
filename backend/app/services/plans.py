from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from app.db.models import Invoice, Message, Workspace
from app.services.time import IST, ensure_utc, next_valid_send_slot, send_at_for_date, today_ist

ALLOWED_PLACEHOLDERS = {
    "{{contact_name}}",
    "{{invoice_number}}",
    "{{amount}}",
    "{{outstanding}}",
    "{{due_date}}",
    "{{business_name}}",
}
CHECKIN_PLACEHOLDERS = ALLOWED_PLACEHOLDERS | {"{{promise_date}}"}
PLACEHOLDER_RE = re.compile(r"\{\{[a-z_]+\}\}")
TONES = {"friendly", "neutral", "firm"}


class PlanValidationError(ValueError):
    pass


@dataclass
class DraftMessageInput:
    send_on: date
    tone: str
    subject: str
    body: str


@dataclass
class PromiseCheckinInput:
    subject: str
    body: str


@dataclass
class ComputedMessage:
    kind: str
    step: int
    tone: str
    subject: str
    body: str
    send_on: date | None
    send_at: datetime | None
    sunday_shifted_to: date | None


def _validate_text_fields(
    *,
    subject: str,
    body: str,
    allowed: set[str],
    field_prefix: str,
) -> None:
    if not subject.strip():
        raise PlanValidationError(f"{field_prefix}.subject is required")
    if not body.strip():
        raise PlanValidationError(f"{field_prefix}.body is required")
    if len(subject) > 120:
        raise PlanValidationError(f"{field_prefix}.subject must be ≤120 characters")
    if len(body) > 1500:
        raise PlanValidationError(f"{field_prefix}.body must be ≤1,500 characters")

    found = set(PLACEHOLDER_RE.findall(subject + "\n" + body))
    unknown = sorted(found - allowed)
    if unknown:
        raise PlanValidationError(
            f"{field_prefix} has unknown placeholders {unknown}; "
            f"allowed: {sorted(allowed)}"
        )


def validate_and_compute_messages(
    *,
    messages: list[DraftMessageInput],
    promise_checkin: PromiseCheckinInput,
    due_date: date,
    workspace: Workspace,
    today: date | None = None,
) -> list[ComputedMessage]:
    if not 1 <= len(messages) <= 6:
        raise PlanValidationError("messages must contain 1–6 items")

    today_value = today or today_ist()
    previous_send_on: date | None = None
    computed: list[ComputedMessage] = []

    for index, message in enumerate(messages, start=1):
        prefix = f"messages[{index}]"
        if message.tone not in TONES:
            raise PlanValidationError(f"{prefix}.tone must be one of {sorted(TONES)}")
        _validate_text_fields(
            subject=message.subject,
            body=message.body,
            allowed=ALLOWED_PLACEHOLDERS,
            field_prefix=prefix,
        )

        send_on = message.send_on
        if send_on < today_value:
            raise PlanValidationError(
                f"{prefix}.send_on must be on or after today_ist {today_value.isoformat()}"
            )
        if send_on > due_date + timedelta(days=60):
            raise PlanValidationError(
                f"{prefix}.send_on must be ≤ due_date + 60 days ({due_date.isoformat()})"
            )
        if previous_send_on is not None and send_on < previous_send_on + timedelta(days=2):
            raise PlanValidationError(
                f"{prefix}.send_on must be at least 2 days after the previous message"
            )

        send_at, shifted_to = send_at_for_date(
            send_on,
            hour_ist=workspace.send_hour_ist,
            minute_ist=workspace.send_minute_ist,
        )
        computed.append(
            ComputedMessage(
                kind="main",
                step=index,
                tone=message.tone,
                subject=message.subject.strip(),
                body=message.body.strip(),
                send_on=shifted_to or send_on,
                send_at=send_at,
                sunday_shifted_to=shifted_to,
            )
        )
        previous_send_on = send_on

    _validate_text_fields(
        subject=promise_checkin.subject,
        body=promise_checkin.body,
        allowed=CHECKIN_PLACEHOLDERS,
        field_prefix="promise_checkin",
    )
    computed.append(
        ComputedMessage(
            kind="promise_checkin",
            step=len(messages) + 1,
            tone="neutral",
            subject=promise_checkin.subject.strip(),
            body=promise_checkin.body.strip(),
            send_on=None,
            send_at=None,
            sunday_shifted_to=None,
        )
    )
    return computed


def bump_past_send_ats(
    messages: Iterable[Message],
    *,
    workspace: Workspace,
    now: datetime,
) -> None:
    now_utc = ensure_utc(now)
    assert now_utc is not None
    for message in messages:
        if message.kind != "main":
            continue
        send_at = ensure_utc(message.send_at)
        if send_at is None or send_at > now_utc:
            continue
        message.send_at = next_valid_send_slot(
            now_utc,
            hour_ist=workspace.send_hour_ist,
            minute_ist=workspace.send_minute_ist,
        )


def respace_held_messages(
    messages: list[Message],
    *,
    workspace: Workspace,
    now: datetime,
    min_gap_days: int = 2,
) -> None:
    """Re-schedule held main messages from the next valid slot, preserving gaps."""
    mains = [m for m in messages if m.kind == "main" and m.status == "held"]
    if not mains:
        return

    now_utc = ensure_utc(now)
    assert now_utc is not None
    mains.sort(key=lambda m: (m.step, ensure_utc(m.send_at) or now_utc))
    original_ats = [ensure_utc(m.send_at) for m in mains]
    cursor = next_valid_send_slot(
        now_utc,
        hour_ist=workspace.send_hour_ist,
        minute_ist=workspace.send_minute_ist,
    )
    mains[0].send_at = cursor
    mains[0].status = "scheduled"

    for index in range(1, len(mains)):
        previous_original = original_ats[index - 1]
        current_original = original_ats[index]
        if previous_original and current_original:
            gap_days = max(
                min_gap_days,
                (
                    current_original.astimezone(IST).date()
                    - previous_original.astimezone(IST).date()
                ).days,
            )
        else:
            gap_days = min_gap_days
        earliest = cursor + timedelta(days=gap_days)
        cursor = next_valid_send_slot(
            earliest,
            hour_ist=workspace.send_hour_ist,
            minute_ist=workspace.send_minute_ist,
        )
        mains[index].send_at = cursor
        mains[index].status = "scheduled"


def outstanding_paise(invoice: Invoice) -> int:
    return max(invoice.amount_paise - invoice.amount_paid_paise, 0)
