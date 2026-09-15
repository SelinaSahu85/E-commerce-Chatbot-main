from database.repositories import CaseRepository
from services import audit_service


def create_case(customer_id, order_id, case_type):

    case = CaseRepository.create_case(customer_id, order_id, case_type)

    audit_service.log(case["case_id"], f"Case created ({case_type})", user="System")

    return case


def get_case(case_id):
    return CaseRepository.get_by_id(case_id)


def update_stage(case_id, current_stage=None, status=None, user="System"):

    CaseRepository.update_stage(case_id, current_stage=current_stage, status=status)

    parts = []

    if current_stage is not None:
        parts.append(f"stage -> {current_stage}")

    if status is not None:
        parts.append(f"status -> {status}")

    if parts:
        audit_service.log(case_id, "Case updated: " + ", ".join(parts), user=user)


def close_case(case_id, reason="Resolution completed", user="System"):

    update_stage(case_id, current_stage="Closed", status="Closed", user=user)

    audit_service.log(case_id, f"Case closed: {reason}", user=user)
