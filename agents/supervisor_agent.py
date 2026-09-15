"""
Supervisor and Case Management Agent.

Orchestrator only: classifies the request as enquiry/complaint and
routes it. It does NOT make refund/replacement/eligibility decisions —
that's the Complaint Resolution Agent's job. Case creation, department
tasking, notifications and closure happen inside the enquiry/complaint
agents and the services/hitl layers they call, driven by
datasets/master_data/workflow_transitions.csv.
"""

from tools.intent_classifier import classify_intent
from utils.logger import logger


def route_query(state):

    query = state["user_query"]

    # A complaint intake spans several turns (order id -> issue type ->
    # description). Once that's in progress, keep routing to the
    # complaint agent instead of re-classifying each follow-up answer.
    if state.get("pending_field"):

        logger.info("Continuing in-progress complaint intake")

        return {"intent": "complaint"}

    logger.info(f"Supervisor received query: {query}")

    intent = classify_intent(query)

    logger.info(f"Detected Intent: {intent}")

    return {
        "intent": intent
    }
