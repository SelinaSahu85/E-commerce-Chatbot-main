"""
Extracts structured data (order id, product, amount, date) from
text-based attachments: PDF invoices/receipts, text documents. Images
and videos are NOT handled here — they are routed to a human evidence
reviewer (see hitl/evidence_review.py). Deterministic extraction, not
an agent.
"""

import re

_ORDER_ID_RE = re.compile(r"\bORD\d{3,}\b", re.IGNORECASE)
_AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s?([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def extract_text_from_pdf(file_path: str) -> str:

    import fitz  # pymupdf

    text_parts = []

    with fitz.open(file_path) as doc:
        for page in doc:
            text_parts.append(page.get_text())

    return "\n".join(text_parts)


def extract_text_from_txt(file_path: str) -> str:

    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_structured_data(text: str) -> dict:

    order_match = _ORDER_ID_RE.search(text or "")
    amount_match = _AMOUNT_RE.search(text or "")
    date_match = _DATE_RE.search(text or "")

    return {
        "order_id": order_match.group(0).upper() if order_match else None,
        "amount": amount_match.group(1).replace(",", "") if amount_match else None,
        "purchase_date": date_match.group(1) if date_match else None,
    }


def process_document(file_path: str) -> dict:
    """
    Processes a PDF or text attachment and returns structured data:
    {order_id, amount, purchase_date}. Unsupported file types raise
    ValueError so the caller can route to a human reviewer instead.
    """

    lower = file_path.lower()

    if lower.endswith(".pdf"):
        text = extract_text_from_pdf(file_path)
    elif lower.endswith(".txt"):
        text = extract_text_from_txt(file_path)
    else:
        raise ValueError(
            f"Unsupported document type for automated processing: {file_path}"
        )

    return extract_structured_data(text)
