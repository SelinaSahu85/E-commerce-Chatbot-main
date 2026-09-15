"""
Generic simulated department-user workflow, used by every department
page (Returns, Warehouse, Inventory, Shipment, Delivery, Finance, ...).
Department users review the recommended next action, approve/reject it,
and the case advances to the next stage per workflow_transitions.csv.
"""

from database.repositories import DepartmentTaskRepository, CaseRepository
from services import department_service, audit_service, case_service


def pending_tasks(department: str):
    return DepartmentTaskRepository.pending_for_department(department)


def approve_task(task_id, user="DepartmentUser"):

    tasks = DepartmentTaskRepository.find_by(task_id=task_id)

    if tasks.empty:
        return {"ok": False, "reason": "Task not found."}

    task = tasks.iloc[0].to_dict()

    case = CaseRepository.get_by_id(task["case_id"])

    if case is None:
        return {"ok": False, "reason": "Case not found."}

    DepartmentTaskRepository.update_status(task_id, "DONE", notes="Approved")

    audit_service.log(
        task["case_id"],
        f"Department task completed: {task['action']} ({task['department']})",
        user=user,
    )

    transition = department_service.advance_case(
        task["case_id"], task["resolution"], case["current_stage"]
    )

    if transition is None:
        return {"ok": False, "reason": "No further workflow transition defined."}

    return {"ok": True, "reason": None}


def reject_task(task_id, reason, user="DepartmentUser"):

    tasks = DepartmentTaskRepository.find_by(task_id=task_id)

    if tasks.empty:
        return {"ok": False, "reason": "Task not found."}

    task = tasks.iloc[0].to_dict()

    DepartmentTaskRepository.update_status(task_id, "REJECTED", notes=reason)

    audit_service.log(
        task["case_id"], f"Department task rejected: {task['action']} ({reason})", user=user
    )

    case_service.update_stage(task["case_id"], status="Escalated")
