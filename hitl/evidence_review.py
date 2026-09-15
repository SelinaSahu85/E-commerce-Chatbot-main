"""
Evidence Reviewer HITL role: reviews product images/videos submitted
for a complaint and marks them Valid, Invalid, Unclear, or requests
better evidence. Text/PDF evidence is instead handled automatically by
tools/document_processor.py.
"""

from database.repositories import EvidenceRepository
from services import audit_service, case_service


def request_evidence(case_id, evidence_type="image", description=""):
    """
    Creates a PENDING evidence review entry and moves the case into the
    Evidence Review stage.
    """

    evidence = EvidenceRepository.create_pending(case_id, evidence_type, description)

    case_service.update_stage(case_id, current_stage="Evidence Review")

    audit_service.log(case_id, f"Evidence submitted for human review ({evidence_type})")

    return evidence


def pending_evidence():
    return EvidenceRepository.pending()


def record_decision(evidence_id, result, comments="", reviewed_by="EvidenceReviewer"):
    """
    result: one of Valid, Invalid, Unclear, Better Evidence Required
    """

    EvidenceRepository.record_decision(evidence_id, result, comments, reviewed_by)

    evidence_rows = EvidenceRepository.find_by(evidence_id=evidence_id)

    if evidence_rows.empty:
        return

    case_id = evidence_rows.iloc[0]["case_id"]

    audit_service.log(
        case_id, f"Evidence reviewed: {result} ({comments})", user=reviewed_by
    )

    # Local import to avoid a circular import (complaint_agent imports
    # this module to request evidence in the first place).
    from agents.complaint_agent import evaluate_and_recommend

    case_service.update_stage(case_id, current_stage="Under Review")

    evaluate_and_recommend(case_id)
