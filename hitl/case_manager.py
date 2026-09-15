"""
Case Manager HITL role: reviews the AI-generated resolution
recommendation for a complaint and approves, modifies, or rejects it.
Approval runs the state revalidator immediately before recording a
refund/replacement/voucher to prevent double-processing.
"""

from database.repositories import (
    CaseRepository,
    ComplaintRepository,
    OrderRepository,
    RefundRepository,
    ReplacementRepository,
    VoucherRepository,
)
from models.resolution import RESOLUTION_TO_WORKFLOW_LABEL
from services import case_service, department_service, notification_service, audit_service
from tools.state_revalidator import revalidate_before_action

_COMPENSATION_RESOLUTIONS = {"refund", "replacement", "voucher"}


def pending_recommendations():

    cases = CaseRepository.all()

    if cases.empty:
        return cases

    return cases[
        (cases["current_stage"] == "Case Approval") & (cases["status"] != "Closed")
    ]


def _create_compensation_record(case, complaint, resolution_type):

    order = OrderRepository.get_by_id(case["order_id"])
    amount = order.get("amount") if order else "0"

    if resolution_type == "refund":
        RefundRepository.create_refund(
            case["case_id"], case["order_id"], case["customer_id"], amount
        )
    elif resolution_type == "replacement":
        ReplacementRepository.create_replacement(
            case["case_id"], case["order_id"], case["customer_id"]
        )
    elif resolution_type == "voucher":
        VoucherRepository.create_voucher(
            case["case_id"], case["customer_id"], amount
        )


def approve(case_id, override_resolution=None, approver="CaseManager"):
    """
    Approves (optionally overriding) the recommended resolution.
    Returns {ok, reason}.
    """

    case = CaseRepository.get_by_id(case_id)
    complaint = ComplaintRepository.get_by_case(case_id)

    if case is None or complaint is None:
        return {"ok": False, "reason": "Case or complaint not found."}

    resolution_type = override_resolution or complaint.get("recommended_resolution")

    if not resolution_type:
        return {"ok": False, "reason": "No recommended resolution on this complaint."}

    # Seed/demo data and older records may store this Capitalized
    # (matching workflow_transitions.csv style); eligibility.py produces
    # lowercase. Normalize so both are accepted.
    resolution_type = resolution_type.strip().lower()

    if override_resolution:
        ComplaintRepository.set_recommended_resolution(case_id, override_resolution)
        audit_service.log(
            case_id, f"Case Manager modified resolution to '{override_resolution}'", user=approver
        )

    if resolution_type in _COMPENSATION_RESOLUTIONS:

        revalidation = revalidate_before_action(case_id, resolution_type)

        if not revalidation["ok"]:
            audit_service.log(
                case_id, f"Approval blocked by state revalidation: {revalidation['reason']}",
                user=approver,
            )
            return {"ok": False, "reason": revalidation["reason"]}

        _create_compensation_record(case, complaint, resolution_type)

    workflow_label = RESOLUTION_TO_WORKFLOW_LABEL.get(resolution_type)

    if workflow_label is None:
        return {"ok": False, "reason": f"Unknown resolution type '{resolution_type}'."}

    audit_service.log(
        case_id, f"Case Manager approved resolution: {resolution_type}", user=approver
    )

    transition = department_service.advance_case(case_id, workflow_label, "Case Approval")

    if transition is None:
        return {
            "ok": False,
            "reason": f"No workflow transition defined for '{workflow_label}' from Case Approval.",
        }

    return {"ok": True, "reason": None}


def reject(case_id, reason, approver="CaseManager"):

    case_service.close_case(case_id, reason=f"Rejected by Case Manager: {reason}", user=approver)

    case = CaseRepository.get_by_id(case_id)

    if case:
        notification_service.notify_customer(
            case_id, case["customer_id"],
            f"Your request has been reviewed and could not be approved. Reason: {reason}",
        )
