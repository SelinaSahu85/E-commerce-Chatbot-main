"""
Deterministic workflow-transition engine.

Drives "what happens next" (department task creation, customer
notification, and case stage/status) from
datasets/master_data/workflow_transitions.csv instead of an LLM decision,
per the MVP design: department task creation and customer status updates
should be deterministic, not model-generated.
"""

from database.repositories import (
    WorkflowTransitionRepository,
    DepartmentTaskRepository,
    RefundRepository,
    ReplacementRepository,
    VoucherRepository,
)
from services import case_service, notification_service, audit_service

# Departments that don't correspond to a simulated department task queue.
# "Case Manager Team" is deliberately excluded here: it's handled by the
# dedicated hitl/case_manager.py review flow (which runs state
# revalidation + creates the compensation record), not the generic
# department task queue.
_NO_TASK_DEPARTMENTS = {"System", "Customer", "Case Manager Team"}

_RESOLUTION_COMPLETION_REPO = {
    "Refund": RefundRepository,
    "Replacement": ReplacementRepository,
}


def create_department_task(case_id, department, action, resolution, notes=""):
    return DepartmentTaskRepository.create_task(
        case_id=case_id,
        department=department,
        action=action,
        resolution=resolution,
        notes=notes,
    )


def advance_case(case_id, resolution_label, current_stage):
    """
    Looks up the (resolution_label, current_stage) transition and, if
    found, applies it: updates the case's stage/status, notifies the
    customer, and creates the next department task (unless the
    responsible party is the system or the customer themselves).

    Returns the transition row dict, or None if no transition is defined
    for this (resolution_label, current_stage) pair.
    """

    transition = WorkflowTransitionRepository.next_step(resolution_label, current_stage)

    if transition is None:
        audit_service.log(
            case_id,
            f"No workflow transition defined for resolution='{resolution_label}' "
            f"stage='{current_stage}'",
        )
        return None

    next_stage = transition["next_stage"]
    department = transition["responsible_department"]
    action = transition["action"]
    case_status = transition["case_status"]
    message = transition["customer_notification"]

    case = case_service.get_case(case_id)

    case_service.update_stage(case_id, current_stage=next_stage, status=case_status)

    notification_service.notify_customer(
        case_id, case["customer_id"] if case else "", message
    )

    if department not in _NO_TASK_DEPARTMENTS:
        create_department_task(case_id, department, action, resolution_label)

    if case_status == "Closed":
        _mark_compensation_completed(case_id, resolution_label)

    return transition


def _mark_compensation_completed(case_id, resolution_label):

    repo = _RESOLUTION_COMPLETION_REPO.get(resolution_label)

    if repo is None:
        return

    rows = repo.find_by(case_id=case_id)

    for _, row in rows.iterrows():
        id_col = [c for c in row.index if c.endswith("_id") and c != "case_id"][0]
        repo.update({id_col: row[id_col]}, {"status": "Completed"})
