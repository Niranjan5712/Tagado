from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.engine import (
    EngineError,
    client_promised,
    client_raised_issue,
    client_reported_payment,
)
from app.services.plans import outstanding_paise
from app.services.public import (
    get_invoice_by_token,
    log_client_view,
    public_payload,
    recently_same_response,
    upi_allowed,
)
from app.services.qr import build_upi_qr_png
from app.services.money import paise_to_inr

router = APIRouter(prefix="/public", tags=["public"])


class RespondRequest(BaseModel):
    type: str
    amount_inr: float | None = None
    paid_on: date | None = None
    reference: str | None = Field(default=None, max_length=120)
    promise_date: date | None = None
    reason: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=1000)


@router.get("/invoices/{token}")
def get_public_invoice(token: str, db: Session = Depends(get_db)) -> dict:
    invoice = get_invoice_by_token(db, token)
    if invoice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found")
    log_client_view(db, invoice)
    # reload events after possible view log
    invoice = get_invoice_by_token(db, token)
    assert invoice is not None
    return public_payload(invoice)


@router.get("/invoices/{token}/upi-qr.png")
def get_upi_qr(token: str, db: Session = Depends(get_db)) -> Response:
    invoice = get_invoice_by_token(db, token)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Payment request not found")
    if not upi_allowed(invoice):
        raise HTTPException(status_code=404, detail="UPI is not available for this invoice")

    workspace = invoice.workspace
    assert workspace is not None and workspace.upi_id
    png = build_upi_qr_png(
        upi_id=workspace.upi_id,
        payee_name=workspace.business_name,
        amount_inr=paise_to_inr(outstanding_paise(invoice)),
        invoice_number=invoice.invoice_number,
    )
    return Response(content=png, media_type="image/png")


@router.post("/invoices/{token}/respond")
def respond_public_invoice(
    token: str,
    payload: RespondRequest,
    db: Session = Depends(get_db),
) -> dict:
    invoice = get_invoice_by_token(db, token)
    if invoice is None:
        raise HTTPException(status_code=404, detail="Payment request not found")

    response_type = payload.type.strip().lower()
    event_map = {
        "paid": "payment_reported",
        "scheduled": "payment_promised",
        "need": "issue_raised",
        "problem": "issue_raised",
    }
    if response_type not in event_map:
        raise HTTPException(status_code=400, detail="Unknown response type")

    if recently_same_response(db, invoice, event_map[response_type]):
        return public_payload(invoice)

    try:
        if response_type == "paid":
            if payload.amount_inr is None or payload.paid_on is None:
                raise HTTPException(status_code=400, detail="Amount and payment date are required")
            amount_paise = int(round(float(payload.amount_inr) * 100))
            if amount_paise <= 0:
                raise HTTPException(status_code=400, detail="Amount must be greater than zero")
            invoice = client_reported_payment(
                db,
                invoice.id,
                amount_paise=amount_paise,
                paid_on=payload.paid_on,
                reference=payload.reference,
            )
        elif response_type == "scheduled":
            if payload.promise_date is None:
                raise HTTPException(status_code=400, detail="Scheduled payment date is required")
            invoice = client_promised(db, invoice.id, promise_date=payload.promise_date)
        elif response_type == "need":
            reason = payload.reason or "Need more information"
            invoice = client_raised_issue(
                db,
                invoice.id,
                kind="need",
                reason=reason,
                note=payload.note,
            )
        else:
            reason = payload.reason or "There is a problem"
            invoice = client_raised_issue(
                db,
                invoice.id,
                kind="problem",
                reason=reason,
                note=payload.note,
            )
    except EngineError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return public_payload(invoice)
