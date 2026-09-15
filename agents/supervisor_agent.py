"""
Supervisor and Case Management Agent.

Responsibilities:
- Analyze a new customer query for intent and safety.
- Route safe enquiries to the Enquiry Agent.
- Route sensitive enquiries to human review.
- Route complaints to the Complaint Agent.
- Preserve active multi-turn complaint workflows.

The Supervisor Agent does not make refund, replacement,
eligibility, evidence, or resolution decisions.
"""

from hitl.customer_care import create_review_request
from tools.query_analyzer import analyze_query
from utils.logger import logger


# =========================================================
# ACTIVE COMPLAINT WORKFLOW FIELDS
# =========================================================

ACTIVE_COMPLAINT_FIELDS = {
    "order_id",
    "new_complaint_issue",
    "image_evidence",
    "evidence_review",
    "issue_type",
    "description",
}


# =========================================================
# SUPERVISOR ROUTER
# =========================================================

def route_query(state):
    """
    Analyze and route the customer request.

    Routing rules:

    1. Active complaint workflow:
       Continue routing to the Complaint Agent without making
       another intent-classification LLM call.

    2. New complaint:
       Route to the Complaint Agent.

    3. Safe enquiry:
       Route to the Enquiry Agent.

    4. Sensitive enquiry:
       Create a HITL review request and route to HITL.
    """

    query = str(
        state.get(
            "user_query",
            "",
        )
    ).strip()

    pending_field = str(
        state.get(
            "pending_field",
            "",
        )
    ).strip().lower()

    logger.info(
        "Supervisor received query: %s",
        query,
    )

    logger.info(
        "Current pending field: %s",
        pending_field,
    )

    # =====================================================
    # CONTINUE AN ACTIVE COMPLAINT WORKFLOW
    # =====================================================

    if pending_field in ACTIVE_COMPLAINT_FIELDS:
        logger.info(
            "Continuing active complaint workflow. "
            "Pending field=%s",
            pending_field,
        )

        return {
            "intent": "complaint",
            "is_safe": True,
            "safety_reason": "",
            "analysis_source": "conversation_state",
            "requires_hitl": False,
            "review_id": "",
        }

    # =====================================================
    # ANALYZE NEW QUERY
    # One tool call performs intent and safety classification.
    # =====================================================

    try:
        analysis = analyze_query(
            query
        )

    except Exception as exc:
        logger.exception(
            "Combined query analysis failed: %s",
            exc,
        )

        return {
            "intent": "hitl",
            "is_safe": False,
            "safety_reason": (
                "The request could not be analyzed safely."
            ),
            "analysis_source": "analysis_error",
            "requires_hitl": True,
            "review_id": "",
            "response": (
                "I could not process this request automatically. "
                "The request requires assistance from our "
                "customer-care team."
            ),
        }

    intent = str(
        analysis.get(
            "intent",
            "enquiry",
        )
    ).strip().lower()

    is_safe = bool(
        analysis.get(
            "is_safe",
            False,
        )
    )

    safety_reason = str(
        analysis.get(
            "safety_reason",
            "",
        )
    ).strip()

    analysis_source = str(
        analysis.get(
            "analysis_source",
            "",
        )
    ).strip()

    logger.info(
        "Combined query analysis completed. "
        "Intent=%s, Safe=%s, Source=%s, Reason=%s",
        intent,
        is_safe,
        analysis_source,
        safety_reason,
    )

    # =====================================================
    # COMPLAINT ROUTING
    # Complaints are handled by the Complaint Agent.
    # =====================================================

    if intent == "complaint":
        logger.info(
            "Routing query to Complaint Agent"
        )

        return {
            "intent": "complaint",
            "is_safe": is_safe,
            "safety_reason": safety_reason,
            "analysis_source": analysis_source,
            "requires_hitl": False,
            "review_id": "",
        }

    # =====================================================
    # SENSITIVE ENQUIRY ROUTING
    # Sensitive enquiries are escalated to HITL.
    # =====================================================

    if intent == "enquiry" and not is_safe:
        logger.warning(
            "Sensitive enquiry detected. "
            "Escalating to human review. Reason=%s",
            safety_reason,
        )

        try:
            review_id = create_review_request(
                query
            )

            logger.info(
                "HITL review request created. "
                "Review ID=%s",
                review_id,
            )

        except Exception as exc:
            logger.exception(
                "Failed to create HITL review request: %s",
                exc,
            )

            review_id = ""

        response = (
            "This request contains information or an action "
            "that requires assistance from our customer-care "
            "team.\n\n"
            "Your request has been forwarded for human review."
        )

        if review_id:
            response += (
                f"\n\n**Review ID:** {review_id}"
            )

        return {
            "intent": "hitl",
            "is_safe": False,
            "safety_reason": safety_reason,
            "analysis_source": analysis_source,
            "requires_hitl": True,
            "review_id": review_id,
            "response": response,
        }

    # =====================================================
    # SAFE ENQUIRY ROUTING
    # =====================================================

    logger.info(
        "Safe enquiry detected. "
        "Routing query to Enquiry Agent."
    )

    return {
        "intent": "enquiry",
        "is_safe": True,
        "safety_reason": "",
        "analysis_source": analysis_source,
        "requires_hitl": False,
        "review_id": "",
    }