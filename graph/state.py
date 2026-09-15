"""
Shared graph state.

GraphState contains data passed between graph nodes for one customer turn.

Cross-turn complaint lifecycle data must be stored in the database.
HITL review pages update the database directly and operate outside
the graph.
"""

from typing import List, TypedDict


class GraphState(TypedDict, total=False):
    # ---------------------------------------------------------
    # Current customer message
    # ---------------------------------------------------------

    user_query: str
    customer_id: str

    # ---------------------------------------------------------
    # Supervisor and enquiry flow
    # ---------------------------------------------------------

    intent: str
    response: str
    sources: List[str]

    # ---------------------------------------------------------
    # Human-in-the-loop review
    # ---------------------------------------------------------

    requires_hitl: bool
    review_id: str
    cache_hit: bool

    # ---------------------------------------------------------
    # Complaint details
    # ---------------------------------------------------------

    case_id: str
    order_id: str
    issue_type: str
    description: str

    complaint_status: str
    pending_field: str

    # ---------------------------------------------------------
    # Evidence details
    # ---------------------------------------------------------

    evidence_id: str
    evidence_path: str
    evidence_required: bool
    evidence_status: str

    # ---------------------------------------------------------
    # Resolution details
    # ---------------------------------------------------------

    replacement_available: bool

    resolution_type: str
    resolution_status: str
    resolution_reason: str

    awaiting_resolution_confirmation: bool
    customer_resolution_confirmed: bool

    # ---------------------------------------------------------
    # Department task details
    # ---------------------------------------------------------

    department: str
    department_task_id: str