from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import Settings, get_settings
from app.db.models import Invoice, Message, Workspace
from app.services.money import format_inr_display
from app.services.plans import outstanding_paise

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
MSME_NOTE_TEMPLATE = (
    "{business_name} is registered as a micro/small enterprise (Udyam {udyam_number}). "
    "Under the MSMED Act, payments to registered micro and small enterprises are due within "
    "the agreed period, not exceeding 45 days."
)

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(enabled_extensions=("html",)),
)


@dataclass
class ComposedEmail:
    to_addrs: list[str]
    cc_addrs: list[str]
    reply_to: str | None
    from_display: str
    subject: str
    html: str
    text: str
    client_page_url: str


def format_display_date(value: date) -> str:
    return f"{value.day} {value.strftime('%b %Y')}"


def fill_placeholders(
    text: str,
    *,
    invoice: Invoice,
    workspace: Workspace,
    promise_date: date | None = None,
) -> str:
    client = invoice.client
    outstanding = outstanding_paise(invoice)
    replacements = {
        "{{contact_name}}": client.contact_name,
        "{{invoice_number}}": invoice.invoice_number,
        "{{amount}}": format_inr_display(invoice.amount_paise),
        "{{outstanding}}": format_inr_display(outstanding),
        "{{due_date}}": format_display_date(invoice.due_date),
        "{{business_name}}": workspace.business_name,
        "{{promise_date}}": format_display_date(promise_date) if promise_date else "",
    }
    result = text
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def body_to_paragraphs(body: str) -> list[str]:
    chunks = re.split(r"\n\s*\n", body.strip())
    paragraphs: list[str] = []
    for chunk in chunks:
        cleaned = " ".join(line.strip() for line in chunk.splitlines() if line.strip())
        if cleaned:
            paragraphs.append(cleaned)
    return paragraphs or [body.strip()]


def compose_message_email(
    *,
    invoice: Invoice,
    message: Message,
    workspace: Workspace,
    settings: Settings | None = None,
) -> ComposedEmail:
    settings = settings or get_settings()
    if invoice.client is None:
        raise ValueError("Invoice client must be loaded before composing email")

    subject = fill_placeholders(
        message.subject,
        invoice=invoice,
        workspace=workspace,
        promise_date=invoice.promise_date,
    )
    body = fill_placeholders(
        message.body,
        invoice=invoice,
        workspace=workspace,
        promise_date=invoice.promise_date,
    )
    paragraphs = body_to_paragraphs(body)
    client_page_url = f"{settings.app_url.rstrip('/')}/p/{invoice.public_token}"
    outstanding = outstanding_paise(invoice)

    msme_note = None
    if message.include_msme_note and workspace.udyam_number:
        msme_note = MSME_NOTE_TEMPLATE.format(
            business_name=workspace.business_name,
            udyam_number=workspace.udyam_number,
        )

    rendered_html = _env.get_template("reminder.html").render(
        subject=subject,
        body_paragraphs=[escape(p) for p in paragraphs],
        msme_note=escape(msme_note) if msme_note else None,
        outstanding_display=format_inr_display(outstanding),
        due_date_display=format_display_date(invoice.due_date),
        client_page_url=client_page_url,
        business_name=escape(workspace.business_name),
    )
    rendered_text = _env.get_template("reminder.txt").render(
        body_paragraphs=paragraphs,
        msme_note=msme_note,
        outstanding_display=format_inr_display(outstanding),
        due_date_display=format_display_date(invoice.due_date),
        client_page_url=client_page_url,
        business_name=workspace.business_name,
    )

    sender = workspace.sender_name or workspace.business_name
    return ComposedEmail(
        to_addrs=[invoice.client.email],
        cc_addrs=list(invoice.client.cc_emails or []),
        reply_to=workspace.reply_to_email,
        from_display=f"{sender} via Tagado",
        subject=subject,
        html=rendered_html,
        text=rendered_text,
        client_page_url=client_page_url,
    )
