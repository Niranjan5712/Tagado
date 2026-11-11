from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    sender_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    reply_to_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    bank_account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ifsc: Mapped[str | None] = mapped_column(String(32), nullable=True)
    upi_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    udyam_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mcp_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    send_hour_ist: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    send_minute_ist: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    logo_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    favicon_data_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    accent_color: Mapped[str] = mapped_column(String(32), nullable=False, default="#0f6e56")
    retention_days_paid: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    retention_keep_audit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    users: Mapped[list[User]] = relationship(back_populates="workspace")
    clients: Mapped[list[Client]] = relationship(back_populates="workspace")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="workspace")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="owner")
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    workspace: Mapped[Workspace] = relationship(back_populates="users")


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (UniqueConstraint("workspace_id", "email", name="uq_clients_workspace_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    cc_emails: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    relationship_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="clients")
    invoices: Mapped[list[Invoice]] = relationship(back_populates="client")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("workspace_id", "invoice_number", name="uq_invoices_workspace_number"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoice_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_paid_paise: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    plan_status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    public_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    promise_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    promise_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    promise_broken: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reported_amount_paise: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reported_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    reported_paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    issue_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    issue_reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    issue_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workspace: Mapped[Workspace] = relationship(back_populates="invoices")
    client: Mapped[Client] = relationship(back_populates="invoices")
    messages: Mapped[list[Message]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="Message.step",
    )
    events: Mapped[list[Event]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="Event.created_at.desc()",
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_status_send_at", "status", "send_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    invoice_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="main")
    step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tone: Mapped[str] = mapped_column(String(32), nullable=False, default="neutral")
    subject: Mapped[str] = mapped_column(String(120), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    include_msme_note: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    invoice: Mapped[Invoice] = relationship(back_populates="messages")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_invoice_created", "invoice_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    invoice_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    invoice: Mapped[Invoice] = relationship(back_populates="events")


class OutboundEmail(Base):
    __tablename__ = "outbound_emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    workspace_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invoice_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_addrs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    cc_addrs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    html: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="reminder")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
