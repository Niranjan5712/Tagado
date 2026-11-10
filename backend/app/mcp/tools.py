from __future__ import annotations

from datetime import date

from app.config import get_settings
from app.mcp.context import current_workspace_name, require_workspace_id
from app.mcp.db import workspace_db
from app.mcp.instance import mcp
from app.mcp.schemas import (
    ClientPayload,
    InvoicePayload,
    MessagePayload,
    PromiseCheckinPayload,
)
from app.services import attention as attention_service
from app.services import clients as clients_service
from app.services import invoices as invoices_service
from app.services.engine import (
    DuplicateInvoiceError,
    EngineError,
    _load_invoice,
    confirm_payment,
    create_invoice_with_plan,
    replace_remaining_messages,
    update_message,
)
from app.services.plans import PlanValidationError
from app.services.stats import compute_client_stats
from app.services.time import format_today_ist

CREATE_INVOICE_DESCRIPTION = (
    "Track an invoice and save a draft follow-up plan. "
    "Also onboards a new client when client_id is omitted and the email is not already in Tagado. "
    "Write 3–5 messages: one a few days before the due date, one on or just after it, "
    "then spaced follow-ups that get gradually clearer, ending with a final message that asks for a payment date. "
    "Also write promise_checkin, sent only if the client commits to a date: a polite check-in referencing "
    "{{promise_date}}. Use placeholders instead of typing amounts and dates. "
    "Saved as draft; the owner approves in Tagado."
)


@mcp.tool(
    name="ping",
    description="Health check for the Tagado MCP connector. Returns the authenticated workspace.",
)
def ping() -> dict[str, str]:
    workspace_id = require_workspace_id()
    workspace_name = current_workspace_name.get() or "unknown"
    return {
        "ok": "true",
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "today_ist": format_today_ist(),
        "summary": f"Connected to Tagado workspace '{workspace_name}'.",
    }


@mcp.tool(
    name="get_client_context",
    description=(
        "Look up a client by name or email before drafting. "
        "Returns payment history and relationship notes. "
        "If found=false, the client is new — create_invoice_with_plan will onboard them."
    ),
)
def get_client_context(query: str) -> dict:
    with workspace_db() as (db, workspace):
        return clients_service.get_context(db, workspace.id, query)


@mcp.tool(
    name="create_invoice_with_plan",
    description=CREATE_INVOICE_DESCRIPTION,
)
def create_invoice_with_plan_tool(
    client: ClientPayload,
    invoice: InvoicePayload,
    messages: list[MessagePayload],
    promise_checkin: PromiseCheckinPayload,
    client_id: str | None = None,
) -> dict:
    settings = get_settings()
    with workspace_db() as (db, workspace):
        try:
            created = create_invoice_with_plan(
                db,
                workspace=workspace,
                client_id=client_id,
                client=client.model_dump(),
                invoice=invoice.model_dump(),
                messages=[item.model_dump() for item in messages],
                promise_checkin=promise_checkin.model_dump(),
            )
        except DuplicateInvoiceError as exc:
            return invoices_service.serialize_created_invoice(
                exc.invoice,
                settings=settings,
                already_tracked=True,
            )
        except (PlanValidationError, EngineError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

        stats = compute_client_stats(db, created.client_id)
        return invoices_service.serialize_created_invoice(
            created,
            settings=settings,
            client_stats={
                "invoices_total": stats.invoices_total,
                "paid_count": stats.paid_count,
                "on_time_pct": stats.on_time_pct,
                "avg_days_late": stats.avg_days_late,
                "broken_promises": stats.broken_promises,
            },
            already_tracked=False,
        )


@mcp.tool(
    name="update_message",
    description=(
        "Edit one unsent follow-up message. Any Claude edit returns the plan to draft "
        "and requires the owner to re-approve in Tagado before anything is sent."
    ),
)
def update_message_tool(
    message_id: str,
    subject: str | None = None,
    body: str | None = None,
    send_on: str | None = None,
) -> dict:
    settings = get_settings()
    with workspace_db() as (db, workspace):
        try:
            message = update_message(
                db,
                message_id,
                subject=subject,
                body=body,
                send_on=date.fromisoformat(send_on) if send_on else None,
                actor="claude",
            )
        except (EngineError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

        invoice = _load_invoice(db, message.invoice_id)
        if invoice.workspace_id != workspace.id:
            raise ValueError("Message not found in this workspace")
        detail = invoices_service.get_invoice(
            db,
            workspace.id,
            invoice_id=invoice.id,
            settings=settings,
        )
        updated = next(item for item in detail["messages"] if item["id"] == message.id)
        return {
            "updated_message": updated,
            "invoice_id": invoice.id,
            "plan_status": invoice.plan_status,
            "review_url": invoices_service.review_url(settings, invoice.id),
            "today_ist": format_today_ist(),
            "summary": (
                f"Updated message on {invoice.invoice_number}. Plan is draft again — "
                f"re-approve in Tagado: {invoices_service.review_url(settings, invoice.id)}"
            ),
        }


@mcp.tool(
    name="replace_remaining_messages",
    description=(
        "Replace unsent follow-ups with a new draft plan after a broken promise, "
        "resolved issue, or change of approach. Requires owner re-approval."
    ),
)
def replace_remaining_messages_tool(
    invoice_id: str,
    messages: list[MessagePayload],
    promise_checkin: PromiseCheckinPayload | None = None,
) -> dict:
    settings = get_settings()
    with workspace_db() as (db, workspace):
        try:
            invoice = replace_remaining_messages(
                db,
                invoice_id,
                messages=[item.model_dump() for item in messages],
                promise_checkin=promise_checkin.model_dump() if promise_checkin else None,
                actor="claude",
            )
        except (PlanValidationError, EngineError, ValueError) as exc:
            raise ValueError(str(exc)) from exc

        if invoice.workspace_id != workspace.id:
            raise ValueError("Invoice not found in this workspace")

        return {
            "invoice_id": invoice.id,
            "plan_status": invoice.plan_status,
            "messages": [
                {
                    "id": message.id,
                    "kind": message.kind,
                    "step": message.step,
                    "status": message.status,
                    "subject": message.subject,
                }
                for message in sorted(invoice.messages, key=lambda item: item.step)
                if message.status == "draft"
            ],
            "review_url": invoices_service.review_url(settings, invoice.id),
            "today_ist": format_today_ist(),
            "summary": (
                f"New draft plan saved for {invoice.invoice_number}. "
                f"Re-approve before sending: {invoices_service.review_url(settings, invoice.id)}"
            ),
        }


@mcp.tool(
    name="list_invoices",
    description="List invoices and totals. Use for questions like who owes money or what is overdue.",
)
def list_invoices_tool(
    status: str = "all",
    client: str | None = None,
) -> dict:
    settings = get_settings()
    with workspace_db() as (db, workspace):
        return invoices_service.list_invoices(
            db,
            workspace.id,
            status=status,
            client=client,
            settings=settings,
        )


@mcp.tool(
    name="get_invoice",
    description="Get one invoice with messages, client response details, timeline events, and review links.",
)
def get_invoice_tool(
    invoice_id: str | None = None,
    invoice_number: str | None = None,
) -> dict:
    settings = get_settings()
    with workspace_db() as (db, workspace):
        try:
            return invoices_service.get_invoice(
                db,
                workspace.id,
                invoice_id=invoice_id,
                invoice_number=invoice_number,
                settings=settings,
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


@mcp.tool(
    name="get_attention_items",
    description="Return invoices that need the owner right now, in priority order.",
)
def get_attention_items_tool() -> dict:
    with workspace_db() as (db, workspace):
        items = attention_service.get_attention_items(db, workspace.id)
        payload = [
            {
                "type": item.type,
                "invoice_id": item.invoice_id,
                "invoice_number": item.invoice_number,
                "client": item.client_name,
                "what_happened": item.summary,
                "owner_options": item.owner_options,
            }
            for item in items
        ]
        return {
            "today_ist": format_today_ist(),
            "items": payload,
            "summary": f"{len(payload)} item(s) need attention." if payload else "Nothing needs attention.",
        }


@mcp.tool(
    name="record_payment",
    description=(
        "Record that the owner explicitly confirmed money was received in the bank. "
        "Only call when the owner confirms payment. Never infer payment."
    ),
)
def record_payment_tool(
    invoice_id: str,
    reference: str | None = None,
    note: str | None = None,
) -> dict:
    with workspace_db() as (db, workspace):
        try:
            invoice = confirm_payment(
                db,
                invoice_id,
                actor="claude_on_owner_instruction",
                reference=reference,
                note=note,
            )
        except EngineError as exc:
            raise ValueError(str(exc)) from exc

        if invoice.workspace_id != workspace.id:
            raise ValueError("Invoice not found in this workspace")

        cancelled = sum(1 for message in invoice.messages if message.status == "cancelled")
        return {
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "cancelled_message_count": cancelled,
            "today_ist": format_today_ist(),
            "summary": (
                f"Marked {invoice.invoice_number} as paid. "
                f"Cancelled {cancelled} unsent reminder(s)."
            ),
        }
