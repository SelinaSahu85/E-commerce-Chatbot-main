"""
LangGraph workflow for the E-Commerce Customer Support Assistant.

Routing:
- Safe enquiry -> Enquiry Agent
- Complaint -> Complaint Agent
- Sensitive enquiry -> End after Supervisor creates HITL request
"""

import sqlite3
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from agents.complaint_agent import complaint_agent
from agents.enquiry_agent import enquiry_agent
from agents.supervisor_agent import route_query
from graph.nodes import ensure_database_ready
from graph.state import GraphState
from utils.logger import logger


# =========================================================
# CHECKPOINT DATABASE
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHECKPOINT_DIRECTORY = (
    PROJECT_ROOT / "db"
)

CHECKPOINT_FILE = (
    CHECKPOINT_DIRECTORY / "checkpoints.db"
)

CHECKPOINT_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)

checkpoint_connection = sqlite3.connect(
    str(CHECKPOINT_FILE),
    check_same_thread=False,
)

checkpointer = SqliteSaver(
    checkpoint_connection
)


# =========================================================
# GRAPH ROUTING
# =========================================================

def select_route(state: GraphState) -> str:
    """
    Select the next node after the Supervisor Agent.

    Expected Supervisor results:

    Safe enquiry:
        intent = enquiry
        is_safe = True
        requires_hitl = False

    Complaint:
        intent = complaint

    Sensitive enquiry:
        intent = hitl
        is_safe = False
        requires_hitl = True
    """

    intent = str(
        state.get(
            "intent",
            "enquiry",
        )
    ).strip().lower()

    requires_hitl = bool(
        state.get(
            "requires_hitl",
            False,
        )
    )

    is_safe = state.get(
        "is_safe",
        True,
    )

    logger.info(
        "Workflow route selection. "
        "Intent=%s, Safe=%s, Requires HITL=%s",
        intent,
        is_safe,
        requires_hitl,
    )

    # Sensitive enquiries already receive their HITL response
    # from the Supervisor Agent. End the graph here.
    if (
        requires_hitl
        or intent == "hitl"
        or is_safe is False
    ):
        logger.info(
            "Routing sensitive request to workflow end "
            "after HITL escalation."
        )

        return "hitl"

    if intent == "complaint":
        logger.info(
            "Routing request to Complaint Agent."
        )

        return "complaint"

    logger.info(
        "Routing request to Enquiry Agent."
    )

    return "enquiry"


# =========================================================
# BUILD WORKFLOW
# =========================================================

workflow = StateGraph(
    GraphState
)

workflow.add_node(
    "bootstrap",
    ensure_database_ready,
)

workflow.add_node(
    "supervisor",
    route_query,
)

workflow.add_node(
    "enquiry",
    enquiry_agent,
)

workflow.add_node(
    "complaint",
    complaint_agent,
)


# =========================================================
# ENTRY POINT
# =========================================================

workflow.set_entry_point(
    "bootstrap"
)


# =========================================================
# GRAPH EDGES
# =========================================================

workflow.add_edge(
    "bootstrap",
    "supervisor",
)

workflow.add_conditional_edges(
    "supervisor",
    select_route,
    {
        "enquiry": "enquiry",
        "complaint": "complaint",
        "hitl": END,
    },
)

workflow.add_edge(
    "enquiry",
    END,
)

workflow.add_edge(
    "complaint",
    END,
)


# =========================================================
# COMPILE GRAPH
# =========================================================

graph = workflow.compile(
    checkpointer=checkpointer
)


# =========================================================
# GRAPH INVOCATION HELPER
# =========================================================

def invoke_graph(
    state: GraphState,
    thread_id: str = "",
):
    """
    Invoke the customer-support graph.

    A new thread ID is created when one is not supplied.

    Supply the same thread ID if LangGraph checkpoint state
    must be reused across multiple turns.
    """

    normalized_thread_id = str(
        thread_id or ""
    ).strip()

    if not normalized_thread_id:
        normalized_thread_id = str(
            uuid4()
        )

    config = {
        "configurable": {
            "thread_id": normalized_thread_id,
        }
    }

    logger.info(
        "Invoking support workflow. Thread ID=%s",
        normalized_thread_id,
    )

    result = graph.invoke(
        state,
        config=config,
    )

    logger.info(
        "Support workflow completed. "
        "Thread ID=%s, Intent=%s, Requires HITL=%s",
        normalized_thread_id,
        result.get("intent"),
        result.get("requires_hitl"),
    )

    return result