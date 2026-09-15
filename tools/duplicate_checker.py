"""
Deterministic duplicate/history check against the case database:
existing open complaints for the order, active refund, active
replacement, and previously issued vouchers for the customer. Critical
duplicate decisions are based on these database checks, not an LLM
judgment.
"""

from database.repositories import (
    CaseRepository,
    ComplaintRepository,
    RefundRepository,
    ReplacementRepository,
    VoucherRepository,
)


def check_duplicate_complaint(order_id: str, customer_id: str = "", exclude_case_id: str = None) -> dict:
    """
    Returns:
    {
        "duplicate": bool,               # an open case already exists for this order
        "existing_case_id": str | None,
        "existing_refund": bool,
        "existing_replacement": bool,
        "existing_voucher": bool,
    }
    """

    open_cases = CaseRepository.open_cases_for_order(order_id, exclude_case_id=exclude_case_id)

    duplicate = not open_cases.empty
    existing_case_id = open_cases.iloc[0]["case_id"] if duplicate else None

    return {
        "duplicate": duplicate,
        "existing_case_id": existing_case_id,
        "existing_refund": RefundRepository.has_active_refund(order_id),
        "existing_replacement": ReplacementRepository.has_active_replacement(order_id),
        "existing_voucher": (
            VoucherRepository.has_previous_voucher(customer_id) if customer_id else False
        ),
    }


def find_existing_open_complaint(order_id: str):
    """
    Returns the existing open complaint row for this order, if any.
    """

    complaints = ComplaintRepository.find_by(order_id=order_id)

    if complaints.empty:
        return None

    open_cases = CaseRepository.open_cases_for_order(order_id)

    if open_cases.empty:
        return None

    open_case_ids = set(open_cases["case_id"].tolist())

    for _, row in complaints.iterrows():
        if row["case_id"] in open_case_ids:
            return row.to_dict()

    return None
