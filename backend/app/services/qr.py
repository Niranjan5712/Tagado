from __future__ import annotations

import io
from urllib.parse import quote

import qrcode


def build_upi_qr_png(
    *,
    upi_id: str,
    payee_name: str,
    amount_inr: float,
    invoice_number: str,
) -> bytes:
    params = (
        f"upi://pay?pa={quote(upi_id)}"
        f"&pn={quote(payee_name)}"
        f"&am={amount_inr:.2f}"
        f"&tn={quote(invoice_number)}"
        f"&cu=INR"
    )
    image = qrcode.make(params)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
