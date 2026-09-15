"""
Guardrail layer: detects sensitive information and blocks unsafe or
unauthorized content before it reaches the customer. Deterministic
regex-based checks, not an agent.
"""

import re

_CARD_NUMBER_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_CVV_RE = re.compile(r"\bcvv\D{0,3}\d{3,4}\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"\b\d{10}\b")

_RESTRICTED_KEYWORDS = [
    "bank account",
    "account deletion",
    "delete my account",
    "card details",
    "card number",
    "cvv",
    "otp",
    "password",
    "consumer court",
    "legal action",
    "lawsuit",
    "police complaint",
]

_UNSUPPORTED_FINANCIAL_ACTIONS = [
    "wire transfer",
    "change bank details",
    "update payment method",
    "process payment manually",
]


def contains_sensitive_info(text: str) -> bool:

    if not text:
        return False

    if _CARD_NUMBER_RE.search(text) or _CVV_RE.search(text):
        return True

    if _EMAIL_RE.search(text) or _PHONE_RE.search(text):
        return True

    return False


def is_restricted_request(text: str) -> bool:

    if not text:
        return False

    lowered = text.lower()

    return any(keyword in lowered for keyword in _RESTRICTED_KEYWORDS)


def requests_unsupported_financial_action(text: str) -> bool:

    if not text:
        return False

    lowered = text.lower()

    return any(keyword in lowered for keyword in _UNSUPPORTED_FINANCIAL_ACTIONS)


def check_guardrails(text: str) -> dict:
    """
    Runs all guardrail checks against a piece of text (customer query or
    a would-be outgoing response). Returns {blocked, reason}.
    """

    if requests_unsupported_financial_action(text):
        return {"blocked": True, "reason": "Unsupported financial action requested."}

    if is_restricted_request(text):
        return {"blocked": True, "reason": "Restricted or sensitive request."}

    if contains_sensitive_info(text):
        return {"blocked": True, "reason": "Message contains sensitive personal information."}

    return {"blocked": False, "reason": None}


def redact_sensitive_info(text: str) -> str:

    if not text:
        return text

    text = _CARD_NUMBER_RE.sub("[REDACTED CARD NUMBER]", text)
    text = _EMAIL_RE.sub("[REDACTED EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED PHONE]", text)

    return text
