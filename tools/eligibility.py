"""
Deterministic policy/eligibility evaluation for complaints.

Combines order delivery date + product return window (products.csv /
orders.csv), the evidence-review result, and the duplicate-check result
to decide the recommended resolution. This is a rules engine, not an
LLM call, per the MVP design principle that eligibility should be based
primarily on deterministic conditions.
"""

from datetime import datetime

_RESOLUTION_MAP = {
    "refund": "refund",
    "return and refund": "refund",
    "replacement": "replacement",
    "return and replacement": "replacement",
    "voucher": "voucher",
    "compensation": "voucher",
}


def _days_since(date_str):

    try:
        delivered = datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None

    return (datetime.now() - delivered).days


def evaluate_eligibility(
    order: dict,
    product: dict,
    requested_resolution: str,
    evidence_result: str,
    duplicate_result: dict,
):
    """
    Returns {resolution_type, reason, policy_reference}.
    resolution_type is one of: refund, replacement, voucher,
    request_better_evidence, reject, escalate.
    """

    if not order:
        return {
            "resolution_type": "escalate",
            "reason": "Order could not be located in the system.",
            "policy_reference": None,
        }

    if duplicate_result and (
        duplicate_result.get("duplicate")
        or duplicate_result.get("existing_refund")
        or duplicate_result.get("existing_replacement")
        or duplicate_result.get("existing_voucher")
    ):
        return {
            "resolution_type": "reject",
            "reason": "A refund, replacement, voucher or complaint already exists for this order.",
            "policy_reference": "Duplicate compensation policy",
        }

    evidence_required = bool(product) and evidence_result is not None

    if evidence_required:

        if evidence_result in (None, "", "Pending"):
            return {
                "resolution_type": "request_better_evidence",
                "reason": "Evidence review is still pending.",
                "policy_reference": None,
            }

        if evidence_result == "Invalid":
            return {
                "resolution_type": "reject",
                "reason": "Submitted evidence was reviewed and found invalid.",
                "policy_reference": "Evidence policy",
            }

        if evidence_result == "Unclear":
            return {
                "resolution_type": "request_better_evidence",
                "reason": "Submitted evidence was unclear; clearer evidence is required.",
                "policy_reference": "Evidence policy",
            }

    return_window_days = None

    if product:
        try:
            return_window_days = int(product.get("return_window_days") or 0)
        except (TypeError, ValueError):
            return_window_days = None

    days_since_delivery = _days_since(order.get("delivery_date"))

    within_window = (
        return_window_days is not None
        and days_since_delivery is not None
        and days_since_delivery <= return_window_days
    )

    resolution_type = _RESOLUTION_MAP.get((requested_resolution or "").strip().lower())

    if not within_window:

        if resolution_type in ("refund", "replacement"):
            return {
                "resolution_type": "reject",
                "reason": (
                    f"Return window of {return_window_days} days has expired "
                    f"({days_since_delivery} days since delivery)."
                ),
                "policy_reference": "Return policy - return window",
            }

        return {
            "resolution_type": "voucher",
            "reason": "Outside the return window; offering a compensation voucher instead.",
            "policy_reference": "Voucher policy",
        }

    if resolution_type in ("refund", "replacement", "voucher"):
        return {
            "resolution_type": resolution_type,
            "reason": (
                f"Within the {return_window_days}-day return window and evidence "
                "review is satisfactory."
            ),
            "policy_reference": f"{resolution_type.capitalize()} policy",
        }

    return {
        "resolution_type": "escalate",
        "reason": "Requested resolution type could not be determined automatically.",
        "policy_reference": None,
    }
