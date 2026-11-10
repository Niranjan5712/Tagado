from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class ClientPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    cc_emails: list[EmailStr] = Field(default_factory=list)
    notes: str | None = None


class InvoicePayload(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=64)
    amount_inr: float = Field(gt=0)
    issue_date: str
    due_date: str
    description: str | None = None
    invoice_url: str | None = None


class MessagePayload(BaseModel):
    send_on: str
    tone: Literal["friendly", "neutral", "firm"]
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)


class PromiseCheckinPayload(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=1500)
