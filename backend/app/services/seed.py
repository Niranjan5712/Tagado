from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import Client, Event, Invoice, Message, OutboundEmail, User, Workspace
from app.services.security import generate_mcp_token, hash_password
from app.services.time import IST, combine_ist_date_time, to_utc

UTC = ZoneInfo("UTC")


def _get_demo_workspace(db: Session, settings: Settings) -> Workspace | None:
    existing_user = db.scalar(select(User).where(User.email == settings.demo_email))
    if existing_user is None:
        return None
    workspace = db.get(Workspace, existing_user.workspace_id)
    if workspace is None:
        raise RuntimeError("Demo user exists without a workspace")
    return workspace


def ensure_demo_workspace(db: Session, settings: Settings) -> Workspace:
    """Create the demo workspace + owner on first boot if missing, then seed demo data once."""
    existing = _get_demo_workspace(db, settings)
    if existing is not None:
        _ensure_workspace_profile(existing, settings)
        if not db.scalar(select(Client.id).where(Client.workspace_id == existing.id).limit(1)):
            seed_demo_business_data(db, existing, settings)
            db.commit()
        return existing

    workspace = Workspace(
        business_name=settings.demo_business_name,
        sender_name=f"{settings.demo_owner_name} at {settings.demo_business_name}",
        reply_to_email=settings.demo_email,
        bank_account_name=f"{settings.demo_business_name}",
        bank_account_number="50200011223344",
        ifsc="HDFC0001234",
        upi_id="pixelcraft@hdfcbank",
        udyam_number="UDYAM-TN-02-0123456",
        mcp_token=generate_mcp_token(),
        is_demo=True,
    )
    db.add(workspace)
    db.flush()

    owner = User(
        email=settings.demo_email,
        password_hash=hash_password(settings.demo_password),
        role="owner",
        name=settings.demo_owner_name,
        workspace_id=workspace.id,
    )
    db.add(owner)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_after_race = _get_demo_workspace(db, settings)
        if existing_after_race is None:
            raise
        return existing_after_race

    db.refresh(workspace)
    seed_demo_business_data(db, workspace, settings)
    db.commit()
    db.refresh(workspace)
    return workspace


def _ensure_workspace_profile(workspace: Workspace, settings: Settings) -> None:
    changed = False
    if not workspace.bank_account_number:
        workspace.bank_account_name = settings.demo_business_name
        workspace.bank_account_number = "50200011223344"
        workspace.ifsc = "HDFC0001234"
        workspace.upi_id = "pixelcraft@hdfcbank"
        workspace.udyam_number = "UDYAM-TN-02-0123456"
        changed = True
    if changed:
        pass  # caller commits when needed


def reset_demo_workspace(db: Session, workspace: Workspace, settings: Settings) -> Workspace:
    if not workspace.is_demo:
        raise RuntimeError("Reset is only allowed for the demo workspace")

    invoice_ids = list(db.scalars(select(Invoice.id).where(Invoice.workspace_id == workspace.id)))
    if invoice_ids:
        db.execute(delete(Event).where(Event.invoice_id.in_(invoice_ids)))
        db.execute(delete(Message).where(Message.invoice_id.in_(invoice_ids)))
        db.execute(delete(OutboundEmail).where(OutboundEmail.workspace_id == workspace.id))
        db.execute(delete(Invoice).where(Invoice.workspace_id == workspace.id))
    db.execute(delete(Client).where(Client.workspace_id == workspace.id))
    db.flush()

    workspace.business_name = settings.demo_business_name
    workspace.sender_name = f"{settings.demo_owner_name} at {settings.demo_business_name}"
    workspace.reply_to_email = settings.demo_email
    workspace.bank_account_name = settings.demo_business_name
    workspace.bank_account_number = "50200011223344"
    workspace.ifsc = "HDFC0001234"
    workspace.upi_id = "pixelcraft@hdfcbank"
    workspace.udyam_number = "UDYAM-TN-02-0123456"
    workspace.mcp_token = generate_mcp_token()

    seed_demo_business_data(db, workspace, settings)
    db.commit()
    db.refresh(workspace)
    return workspace


def seed_demo_business_data(db: Session, workspace: Workspace, settings: Settings) -> None:
    """Seed relationship-aware Indian clients + a few live invoices for the dashboard."""
    today = datetime.now(tz=IST).date()

    kalpataru = Client(
        workspace_id=workspace.id,
        name="Kalpataru Retail Pvt Ltd",
        contact_name="Rahul Mehta",
        email="rahul.mehta@kalpataru-retail.example",
        cc_emails=["accounts@kalpataru-retail.example"],
        relationship_notes=(
            "Client since 2021. Rahul is easy to work with; their accounts team slows down at month-end. "
            "Keep the tone warm and brief."
        ),
    )
    aarohan = Client(
        workspace_id=workspace.id,
        name="Aarohan Logistics Pvt Ltd",
        contact_name="Anita Iyer",
        email="anita.iyer@aarohan-logistics.example",
        cc_emails=["ap@aarohan-logistics.example"],
        relationship_notes=(
            "Often says payment is 'processing'. Be polite, but ask for a specific date and name the delay."
        ),
    )
    prakriti = Client(
        workspace_id=workspace.id,
        name="Prakriti Foods Pvt Ltd",
        contact_name="Karan Shah",
        email="karan.shah@prakriti-foods.example",
        cc_emails=[],
        relationship_notes=None,
    )
    db.add_all([kalpataru, aarohan, prakriti])
    db.flush()

    # Historical paid invoices for relationship stats (Kalpataru: mostly on time)
    for index, days_late in enumerate([0, 0, 2, 0, 0, 5], start=1):
        due = today - timedelta(days=40 * index)
        paid_on = due + timedelta(days=days_late)
        _add_paid_invoice(
            db,
            workspace=workspace,
            client=kalpataru,
            number=f"PX-1{index:03d}",
            amount_paise=1_50_000_00 + index * 10_000_00,
            due=due,
            paid_on=paid_on,
        )

    # Aarohan: often late, two broken promises
    for index, (days_late, broken) in enumerate(
        [(45, True), (30, True), (12, False), (0, False)],
        start=1,
    ):
        due = today - timedelta(days=50 * index)
        paid_on = due + timedelta(days=days_late)
        inv = _add_paid_invoice(
            db,
            workspace=workspace,
            client=aarohan,
            number=f"PX-2{index:03d}",
            amount_paise=2_00_000_00 + index * 15_000_00,
            due=due,
            paid_on=paid_on,
        )
        if broken:
            inv.promise_broken = True
            inv.promise_count = 1

    # Prakriti: both on time
    for index in (1, 2):
        due = today - timedelta(days=25 * index)
        _add_paid_invoice(
            db,
            workspace=workspace,
            client=prakriti,
            number=f"PX-3{index:03d}",
            amount_paise=80_000_00,
            due=due,
            paid_on=due - timedelta(days=1),
        )

    # Live invoices for a non-empty dashboard
    open_prakriti = Invoice(
        workspace_id=workspace.id,
        client_id=prakriti.id,
        invoice_number="PX-2101",
        description="Packaging design refresh",
        amount_paise=95_000_00,
        issue_date=today - timedelta(days=10),
        due_date=today + timedelta(days=12),
        status="open",
        plan_status="active",
        public_token=secrets.token_urlsafe(24),
    )
    db.add(open_prakriti)
    db.flush()
    send_day = today + timedelta(days=3)
    db.add(
        Message(
            invoice_id=open_prakriti.id,
            kind="main",
            step=1,
            tone="friendly",
            subject="Quick note on invoice {{invoice_number}}",
            body="Hi {{contact_name}}, just a heads-up that {{invoice_number}} for {{amount}} is due on {{due_date}}.",
            send_at=to_utc(combine_ist_date_time(send_day, 10, 30)),
            status="scheduled",
        )
    )
    db.add(
        Message(
            invoice_id=open_prakriti.id,
            kind="promise_checkin",
            step=2,
            tone="neutral",
            subject="Checking in on {{promise_date}}",
            body="Hi {{contact_name}}, checking whether {{invoice_number}} went out on {{promise_date}}.",
            status="draft",
        )
    )
    _event(db, open_prakriti.id, "system", "seeded_open_active")

    reported = Invoice(
        workspace_id=workspace.id,
        client_id=prakriti.id,
        invoice_number="PX-2098",
        description="Label set for festive SKUs",
        amount_paise=42_000_00,
        issue_date=today - timedelta(days=25),
        due_date=today - timedelta(days=5),
        status="payment_reported",
        plan_status="active",
        public_token=secrets.token_urlsafe(24),
        reported_at=datetime.now(tz=UTC),
        reported_amount_paise=42_000_00,
        reported_reference="UTR Prakriti 889900",
        reported_paid_on=today - timedelta(days=1),
    )
    db.add(reported)
    db.flush()
    _event(db, reported.id, "client", "payment_reported", {"reference": "UTR Prakriti 889900"})

    issue_inv = Invoice(
        workspace_id=workspace.id,
        client_id=aarohan.id,
        invoice_number="PX-2088",
        description="Brand film edit package",
        amount_paise=2_36_000_00,
        issue_date=today - timedelta(days=20),
        due_date=today - timedelta(days=2),
        status="issue_raised",
        plan_status="paused",
        public_token=secrets.token_urlsafe(24),
        issue_kind="need",
        issue_reason="PO number missing",
        issue_note="Accounts cannot process without PO on the invoice PDF.",
    )
    db.add(issue_inv)
    db.flush()
    db.add(
        Message(
            invoice_id=issue_inv.id,
            kind="main",
            step=1,
            tone="firm",
            subject="Need a payment date for {{invoice_number}}",
            body="Hi {{contact_name}}, {{invoice_number}} for {{outstanding}} is overdue. Please share a payment date.",
            send_at=to_utc(combine_ist_date_time(today + timedelta(days=2), 10, 30)),
            status="held",
        )
    )
    _event(db, issue_inv.id, "client", "issue_raised", {"reason": "PO number missing"})

    paid_recent = Invoice(
        workspace_id=workspace.id,
        client_id=kalpataru.id,
        invoice_number="PX-2075",
        description="Store launch social kit",
        amount_paise=1_20_000_00,
        amount_paid_paise=1_20_000_00,
        issue_date=today - timedelta(days=40),
        due_date=today - timedelta(days=10),
        status="paid",
        plan_status="completed",
        public_token=secrets.token_urlsafe(24),
        paid_at=datetime.now(tz=UTC) - timedelta(days=6),
    )
    db.add(paid_recent)
    db.flush()
    _event(db, paid_recent.id, "owner", "payment_confirmed")


def _add_paid_invoice(
    db: Session,
    *,
    workspace: Workspace,
    client: Client,
    number: str,
    amount_paise: int,
    due: date,
    paid_on: date,
) -> Invoice:
    invoice = Invoice(
        workspace_id=workspace.id,
        client_id=client.id,
        invoice_number=number,
        description="Historical project invoice",
        amount_paise=amount_paise,
        amount_paid_paise=amount_paise,
        issue_date=due - timedelta(days=15),
        due_date=due,
        status="paid",
        plan_status="completed",
        public_token=secrets.token_urlsafe(24),
        paid_at=datetime(paid_on.year, paid_on.month, paid_on.day, 12, 0, tzinfo=IST).astimezone(UTC),
    )
    db.add(invoice)
    db.flush()
    return invoice


def _event(
    db: Session,
    invoice_id: str,
    actor: str,
    event_type: str,
    data: dict | None = None,
) -> None:
    db.add(Event(invoice_id=invoice_id, actor=actor, type=event_type, data=data))


def get_workspace_by_mcp_token(db: Session, token: str) -> Workspace | None:
    if not token:
        return None
    return db.scalar(select(Workspace).where(Workspace.mcp_token == token))
