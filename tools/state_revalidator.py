"""
Rechecks the latest case/refund/replacement/voucher state immediately
before recording a refund, replacement or voucher, to prevent a
double-action (e.g. two refunds) if the state changed between the AI
recommendation and the human approval. Deterministic, not an agent.
"""

from database.repositories import (
    CaseRepository,
    RefundRepository,
    ReplacementRepository,
    VoucherRepository,
)

_ACTIVE_CHECK = {
    "refund": lambda order_id, customer_id: RefundRepository.has_active_refund(order_id),
    "replacement": lambda order_id, customer_id: ReplacementRepository.has_active_replacement(order_id),
    "voucher": lambda order_id, customer_id: VoucherRepository.has_previous_voucher(customer_id),
}


def revalidate_before_action(case_id: str, resolution_type: str) -> dict:
    """
    Returns {"ok": bool, "reason": str | None}. ok=False means the action
    must be stopped (e.g. an existing refund was found for this order).
    """

    case = CaseRepository.get_by_id(case_id)

    if case is None:
        return {"ok": False, "reason": f"Case {case_id} not found."}

    if case.get("status") == "Closed":
        return {"ok": False, "reason": "Case is already closed."}

    check = _ACTIVE_CHECK.get(resolution_type)

    if check is None:
        return {"ok": True, "reason": None}

    if check(case.get("order_id"), case.get("customer_id")):
        return {
            "ok": False,
            "reason": f"An active {resolution_type} already exists for this order/customer.",
        }

    return {"ok": True, "reason": None}
