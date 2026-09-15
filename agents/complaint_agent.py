import os
import re

from database.repositories import (
    ComplaintRepository,
    DepartmentTaskRepository,
)
from tools.complaint_classifier import classify_complaint_issue
from tools.complaint_lookup import lookup_complaint_data
from utils.logger import logger


# =========================================================
# COMPLAINT AND EVIDENCE RULES
# =========================================================

UNRESOLVED_COMPLAINT_STATUSES = {
    "OPEN",
    "IN_PROGRESS",
    "AWAITING_CUSTOMER",
    "COLLECTING_INFORMATION",
    "AWAITING_EVIDENCE",
    "AWAITING_EVIDENCE_REVIEW",
    "EVIDENCE_APPROVED",
    "AWAITING_CUSTOMER_CONFIRMATION",
}

EVIDENCE_REQUIRED_ISSUES = {
    "DAMAGED_PRODUCT",
    "DEFECTIVE_PRODUCT",
    "WRONG_ITEM",
    "MISSING_ITEM",
}

EVIDENCE_NOT_SUBMITTED_STATUSES = {
    "",
    "N/A",
    "REQUESTED",
    "REQUIRED",
    "NOT_SUBMITTED",
}

EVIDENCE_UNDER_REVIEW_STATUSES = {
    "UPLOADED",
    "PENDING",
    "PENDING_REVIEW",
    "UNDER_REVIEW",
}

EVIDENCE_COMPLETED_STATUSES = {
    "APPROVED",
    "REJECTED",
    "INVALID",
}

VALID_RESOLUTION_TYPES = {
    "RETURN",
    "REFUND",
    "REPLACEMENT",
}

YES_RESPONSES = {
    "YES",
    "Y",
    "OK",
    "OKAY",
    "CONFIRM",
    "CONFIRMED",
    "PROCEED",
    "YES PLEASE",
    "PLEASE PROCEED",
    "SURE",
}

NO_RESPONSES = {
    "NO",
    "N",
    "DECLINE",
    "DECLINED",
    "CANCEL",
    "DO NOT PROCEED",
    "DON'T PROCEED",
    "NO THANKS",
}


def normalize_customer_answer(value):
    """
    Normalize a customer's Yes or No response.

    Examples:
        " yes "       becomes "YES"
        "Yes please"  becomes "YES PLEASE"
        "don't proceed" becomes "DON'T PROCEED"
    """

    return " ".join(
        str(value or "")
        .strip()
        .upper()
        .split()
    )


def get_resolution_department(resolution_type):
    """
    Return the department responsible for a confirmed
    resolution.
    """

    department_mapping = {
        "RETURN": "RETURNS",
        "REFUND": "REFUNDS",
        "REPLACEMENT": "REPLACEMENTS",
    }

    return department_mapping.get(
        normalize_status(resolution_type),
        "",
    )


def get_resolution_action(resolution_type):
    """
    Return the department action for a confirmed resolution.
    """

    action_mapping = {
        "RETURN": "Process product return",
        "REFUND": "Process customer refund",
        "REPLACEMENT": "Process product replacement",
    }

    return action_mapping.get(
        normalize_status(resolution_type),
        "Process customer resolution",
    )


def get_active_department_task(case_id):
    """
    Return an existing active department task for the case.

    This prevents duplicate tasks during Streamlit reruns.
    """

    existing_tasks = DepartmentTaskRepository.find_by(
        case_id=case_id
    )

    if existing_tasks.empty:
        return None

    completed_statuses = {
        "COMPLETED",
        "CANCELLED",
        "REJECTED",
    }

    active_tasks = existing_tasks[
        ~existing_tasks["status"]
        .astype(str)
        .str.strip()
        .str.upper()
        .isin(completed_statuses)
    ].copy()

    if active_tasks.empty:
        return None

    return active_tasks.iloc[0].to_dict()

# =========================================================
# BASIC HELPERS
# =========================================================

def clean_value(value):
    """
    Convert a value into a safe display string.
    """

    if value is None:
        return "N/A"

    cleaned_value = str(value).strip()

    if (
        not cleaned_value
        or cleaned_value.lower() == "nan"
    ):
        return "N/A"

    return cleaned_value


def normalize_status(value):
    """
    Convert status and issue values to uppercase.
    """

    cleaned_value = clean_value(value)

    if cleaned_value == "N/A":
        return ""

    return cleaned_value.upper()


def stored_boolean_is_true(value):
    """
    Convert CSV Boolean values into a Python Boolean.
    """

    return normalize_status(value) in {
        "TRUE",
        "YES",
        "Y",
        "1",
    }


def extract_order_id(message):
    """
    Extract and normalize an Order ID from a message.

    Examples:
        ORD5001
        ord5001
        ORD-5001
        ORD 5001
        My order ID is ORD5001
    """

    normalized_message = str(
        message or ""
    ).strip().upper()

    match = re.search(
        r"\bORD[-_\s]?\d+\b",
        normalized_message,
    )

    if not match:
        return ""

    return re.sub(
        r"[-_\s]",
        "",
        match.group(0),
    )


# =========================================================
# EVIDENCE RULES
# =========================================================

def issue_requires_evidence(issue_type):
    """
    Check whether an issue type requires image evidence.
    """

    return (
        normalize_status(issue_type)
        in EVIDENCE_REQUIRED_ISSUES
    )


def should_request_evidence(complaint):
    """
    Decide whether the customer must upload evidence.

    Evidence is requested when:
        1. The complaint issue requires evidence.
        2. Evidence has not been submitted.
        3. The complaint has not been resolved or closed.
    """

    if not complaint:
        return False

    complaint_status = normalize_status(
        complaint.get("complaint_status")
    )

    issue_type = normalize_status(
        complaint.get("issue_type")
    )

    evidence_status = normalize_status(
        complaint.get("evidence_status")
    )

    complaint_is_unresolved = (
        complaint_status
        not in {
            "RESOLVED",
            "CLOSED",
            "CANCELLED",
        }
    )

    issue_needs_evidence = (
        issue_type
        in EVIDENCE_REQUIRED_ISSUES
    )

    evidence_not_submitted = (
        evidence_status
        in EVIDENCE_NOT_SUBMITTED_STATUSES
    )

    evidence_required = (
        complaint_is_unresolved
        and issue_needs_evidence
        and evidence_not_submitted
    )

    logger.info(
        "Evidence rule evaluated. "
        "Complaint status=%s, Issue type=%s, "
        "Evidence status=%s, Required=%s",
        complaint_status,
        issue_type,
        evidence_status,
        evidence_required,
    )

    return evidence_required


def evidence_is_under_review(complaint):
    """
    Check whether evidence is waiting for human review.
    """

    if not complaint:
        return False

    evidence_status = normalize_status(
        complaint.get("evidence_status")
    )

    return (
        evidence_status
        in EVIDENCE_UNDER_REVIEW_STATUSES
    )


def resolution_confirmation_is_pending(complaint):
    """
    Check whether the customer must confirm a recommended
    return, refund, or replacement.
    """

    if not complaint:
        return False

    resolution_type = normalize_status(
        complaint.get("resolution_type")
    )

    resolution_status = normalize_status(
        complaint.get("resolution_status")
    )

    awaiting_confirmation = stored_boolean_is_true(
        complaint.get(
            "awaiting_resolution_confirmation"
        )
    )

    return (
        awaiting_confirmation
        and resolution_status == "RECOMMENDED"
        and resolution_type in VALID_RESOLUTION_TYPES
    )


# =========================================================
# CUSTOMER-FRIENDLY EVIDENCE REQUEST
# =========================================================

def build_fallback_evidence_message(
    customer,
    order,
    complaint,
):
    """
    Return a customer-friendly fallback message when the LLM
    is unavailable.
    """

    customer_name = clean_value(
        customer.get("customer_name")
    )

    if customer_name == "N/A":
        customer_name = "Customer"

    product_name = clean_value(
        order.get("product_name")
    )

    if product_name == "N/A":
        product_name = "your product"

    case_id = clean_value(
        complaint.get("case_id")
    )

    complaint_status = clean_value(
        complaint.get("complaint_status")
    )

    return (
        f"Thank you, {customer_name}. I found your complaint "
        f"for **{product_name}**.\n\n"
        f"Your case ID is **{case_id}**, and the complaint is "
        f"currently **{complaint_status}**.\n\n"
        "Please upload a clear image showing the product and "
        "the affected area. This will help our customer-care "
        "team verify the reported issue.\n\n"
        "After submission, the image will be sent to a human "
        "reviewer for approval."
    )


def generate_customer_friendly_evidence_message(
    customer,
    order,
    complaint,
):
    """
    Use Gemini to generate a customer-friendly evidence request.

    If Gemini is unavailable, return the fallback message.
    """

    fallback_message = build_fallback_evidence_message(
        customer=customer,
        order=order,
        complaint=complaint,
    )

    api_key = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if not api_key:
        logger.warning(
            "GEMINI_API_KEY is not configured. "
            "Using fallback evidence message."
        )

        return fallback_message

    try:
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
        )

        llm = ChatGoogleGenerativeAI(
            model=os.getenv(
                "GEMINI_MODEL",
                "gemini-2.0-flash",
            ),
            google_api_key=api_key,
        )

        customer_name = clean_value(
            customer.get("customer_name")
        )

        product_name = clean_value(
            order.get("product_name")
        )

        case_id = clean_value(
            complaint.get("case_id")
        )

        issue_type = clean_value(
            complaint.get("issue_type")
        )

        complaint_status = clean_value(
            complaint.get("complaint_status")
        )

        evidence_status = clean_value(
            complaint.get("evidence_status")
        )

        prompt = f"""
You are an e-commerce customer support assistant.

Write a brief, professional, and empathetic response.

Customer name: {customer_name}
Product: {product_name}
Case ID: {case_id}
Issue type: {issue_type}
Complaint status: {complaint_status}
Evidence status: {evidence_status}

Instructions:
1. Confirm that the complaint is unresolved.
2. Ask the customer to upload a clear image.
3. Explain that a human reviewer will review the image.
4. Explain that the evidence may be approved or rejected.
5. Do not promise a refund, replacement, or voucher.
6. Do not ask for the Order ID again.
7. Keep the response under 100 words.
"""

        llm_result = llm.invoke(prompt)

        generated_message = str(
            getattr(
                llm_result,
                "content",
                llm_result,
            )
        ).strip()

        if not generated_message:
            logger.warning(
                "LLM returned an empty response. "
                "Using fallback message."
            )

            return fallback_message

        return generated_message

    except Exception as exc:
        logger.exception(
            "LLM evidence response failed: %s",
            exc,
        )

        return fallback_message


# =========================================================
# RESPONSE BUILDERS
# =========================================================

def build_order_response(context):
    """
    Build customer, order, delivery, and complaint information.
    """

    order = context.get("order") or {}
    customer = context.get("customer") or {}
    complaint = context.get("complaint")

    response = [
        "✅ **Order found successfully**"
    ]

    if customer:
        response.extend(
            [
                "### 👤 Customer Information",
                (
                    f"**Customer ID:** "
                    f"{clean_value(customer.get('customer_id'))}"
                ),
                (
                    f"**Customer Name:** "
                    f"{clean_value(customer.get('customer_name'))}"
                ),
                (
                    f"**Email:** "
                    f"{clean_value(customer.get('email'))}"
                ),
                (
                    f"**Phone:** "
                    f"{clean_value(customer.get('phone'))}"
                ),
                (
                    f"**City:** "
                    f"{clean_value(customer.get('city'))}"
                ),
                (
                    f"**State:** "
                    f"{clean_value(customer.get('state'))}"
                ),
                (
                    f"**Loyalty Tier:** "
                    f"{clean_value(customer.get('loyalty_tier'))}"
                ),
            ]
        )

    response.extend(
        [
            "### 📦 Order Information",
            (
                f"**Order ID:** "
                f"{clean_value(order.get('order_id'))}"
            ),
            (
                f"**Product:** "
                f"{clean_value(order.get('product_name'))}"
            ),
            (
                f"**Product ID:** "
                f"{clean_value(order.get('product_id'))}"
            ),
            (
                f"**Category:** "
                f"{clean_value(order.get('category'))}"
            ),
            (
                f"**Quantity:** "
                f"{clean_value(order.get('quantity'))}"
            ),
            (
                f"**Order Amount:** ₹"
                f"{clean_value(order.get('order_amount'))}"
            ),
            (
                f"**Payment Method:** "
                f"{clean_value(order.get('payment_method'))}"
            ),
            (
                f"**Order Date:** "
                f"{clean_value(order.get('order_date'))}"
            ),
            (
                f"**Order Status:** "
                f"{clean_value(order.get('order_status'))}"
            ),
            "### 🚚 Delivery Information",
            (
                f"**Delivery Status:** "
                f"{clean_value(order.get('delivery_status'))}"
            ),
            (
                f"**Delivery Date:** "
                f"{clean_value(order.get('delivery_date'))}"
            ),
        ]
    )

    if complaint:
        response.extend(
            [
                "### 📋 Existing Complaint Information",
                (
                    f"**Complaint ID:** "
                    f"{clean_value(complaint.get('complaint_id'))}"
                ),
                (
                    f"**Case ID:** "
                    f"{clean_value(complaint.get('case_id'))}"
                ),
                (
                    f"**Issue Type:** "
                    f"{clean_value(complaint.get('issue_type'))}"
                ),
                (
                    f"**Description:** "
                    f"{clean_value(complaint.get('description'))}"
                ),
                (
                    f"**Complaint Status:** "
                    f"{clean_value(complaint.get('complaint_status'))}"
                ),
                (
                    f"**Priority:** "
                    f"{clean_value(complaint.get('priority'))}"
                ),
                (
                    f"**Assigned Department:** "
                    f"{clean_value(complaint.get('assigned_department'))}"
                ),
                (
                    f"**Evidence Status:** "
                    f"{clean_value(complaint.get('evidence_status'))}"
                ),
                (
                    f"**Resolution Type:** "
                    f"{clean_value(complaint.get('resolution_type'))}"
                ),
                (
                    f"**Resolution Status:** "
                    f"{clean_value(complaint.get('resolution_status'))}"
                ),
                (
                    f"**Complaint Created:** "
                    f"{clean_value(complaint.get('created_at'))}"
                ),
                (
                    f"**Last Updated:** "
                    f"{clean_value(complaint.get('updated_at'))}"
                ),
            ]
        )

    else:
        response.extend(
            [
                "### 📋 Complaint Information",
                "No existing complaint was found for this order.",
                (
                    "The order has been verified successfully. "
                    "I can help you register a complaint for the "
                    "issue you reported."
                ),
            ]
        )

    return "\n\n".join(response)


def build_evidence_under_review_response(
    order_id,
    complaint,
):
    """
    Return a message while evidence is waiting for human review.
    """

    case_id = clean_value(
        complaint.get("case_id")
    )

    return (
        "### 🔎 Evidence Under Human Review\n\n"
        f"Your image for case **{case_id}** and order "
        f"**{order_id}** has been submitted successfully.\n\n"
        "A customer-care reviewer is currently reviewing the "
        "uploaded evidence. The complaint will be updated after "
        "the reviewer completes the decision."
    )


def build_resolution_confirmation_response(
    order_id,
    complaint,
):
    """
    Ask the customer to confirm the recommended resolution.
    """

    case_id = clean_value(
        complaint.get("case_id")
    )

    resolution_type = normalize_status(
        complaint.get("resolution_type")
    )

    resolution_reason = clean_value(
        complaint.get("resolution_reason")
    )

    resolution_label = resolution_type.lower()

    message = (
        "### ✅ Evidence Approved\n\n"
        "Your uploaded evidence has been approved.\n\n"
        f"**Case ID:** {case_id}\n\n"
        f"**Order ID:** {order_id}\n\n"
        f"**Recommended Resolution:** {resolution_type}\n\n"
    )

    if resolution_reason != "N/A":
        message += (
            f"**Reason:** {resolution_reason}\n\n"
        )

    message += (
        f"Would you like to proceed with the "
        f"**{resolution_label}**?\n\n"
        "Please reply **Yes** or **No**."
    )

    return message


def build_evidence_decision_response(
    order_id,
    complaint,
):
    """
    Return the customer response after evidence approval
    or rejection.
    """

    case_id = clean_value(
        complaint.get("case_id")
    )

    evidence_status = normalize_status(
        complaint.get("evidence_status")
    )

    resolution_status = normalize_status(
        complaint.get("resolution_status")
    )

    if (
        evidence_status == "APPROVED"
        and resolution_confirmation_is_pending(complaint)
    ):
        return build_resolution_confirmation_response(
            order_id,
            complaint,
        )

    if evidence_status == "APPROVED":
        if resolution_status in {
            "",
            "NOT_STARTED",
            "PENDING",
        }:
            return (
                "### ✅ Image Evidence Approved\n\n"
                "Your uploaded image has been approved by our "
                "customer-care reviewer.\n\n"
                f"**Case ID:** {case_id}\n\n"
                f"**Order ID:** {order_id}\n\n"
                "The appropriate return, refund, or replacement "
                "resolution is now being determined.\n\n"
                "Your complaint has not yet been assigned to a "
                "department."
            )

        return (
            "### ✅ Image Evidence Approved\n\n"
            "Your uploaded image has been approved.\n\n"
            f"**Case ID:** {case_id}\n\n"
            f"**Order ID:** {order_id}\n\n"
            f"**Resolution Status:** "
            f"{resolution_status or 'PENDING'}"
        )

    if evidence_status in {
        "REJECTED",
        "INVALID",
    }:
        return (
            "### ❌ Image Evidence Not Approved\n\n"
            "The uploaded image could not be approved by our "
            "customer-care reviewer.\n\n"
            f"**Case ID:** {case_id}\n\n"
            f"**Order ID:** {order_id}\n\n"
            "Please upload a clearer image showing the product "
            "and the reported issue."
        )

    return build_evidence_under_review_response(
        order_id,
        complaint,
    )


def build_status_response(
    order_id,
    complaint,
):
    """
    Return the latest complaint status.
    """

    if not complaint:
        return (
            f"No complaint is currently registered for order "
            f"**{order_id}**.\n\n"
            "The order is verified, and I can help you register "
            "a complaint."
        )

    evidence_status = normalize_status(
        complaint.get("evidence_status")
    )

    if should_request_evidence(complaint):
        return (
            "### 📷 Image Evidence Required\n\n"
            "Supporting evidence has not yet been submitted for "
            "this complaint.\n\n"
            "Please upload a clear image showing the product and "
            "the reported issue."
        )

    if evidence_is_under_review(complaint):
        return build_evidence_under_review_response(
            order_id,
            complaint,
        )

    if evidence_status in EVIDENCE_COMPLETED_STATUSES:
        return build_evidence_decision_response(
            order_id,
            complaint,
        )

    return (
        "### 📋 Latest Complaint Status\n\n"
        f"**Order ID:** {order_id}\n\n"
        f"**Case ID:** "
        f"{clean_value(complaint.get('case_id'))}\n\n"
        f"**Complaint Status:** "
        f"{clean_value(complaint.get('complaint_status'))}\n\n"
        f"**Assigned Department:** "
        f"{clean_value(complaint.get('assigned_department'))}\n\n"
        f"**Evidence Status:** "
        f"{clean_value(complaint.get('evidence_status'))}\n\n"
        f"**Resolution Type:** "
        f"{clean_value(complaint.get('resolution_type'))}\n\n"
        f"**Resolution Status:** "
        f"{clean_value(complaint.get('resolution_status'))}"
    )


# =========================================================
# STATE UPDATE HELPERS
# =========================================================

def update_state_from_complaint(
    state,
    complaint,
):
    """
    Copy complaint values into GraphState.
    """

    case_id = clean_value(
        complaint.get("case_id")
    )

    issue_type = clean_value(
        complaint.get("issue_type")
    )

    complaint_status = clean_value(
        complaint.get("complaint_status")
    )

    complaint_description = clean_value(
        complaint.get("description")
    )

    resolution_type = clean_value(
        complaint.get("resolution_type")
    )

    resolution_status = clean_value(
        complaint.get("resolution_status")
    )

    resolution_reason = clean_value(
        complaint.get("resolution_reason")
    )

    assigned_department = clean_value(
        complaint.get("assigned_department")
    )

    department_task_id = clean_value(
        complaint.get("department_task_id")
    )

    state["case_id"] = (
        "" if case_id == "N/A" else case_id
    )

    state["issue_type"] = (
        "" if issue_type == "N/A" else issue_type
    )

    state["complaint_status"] = (
        ""
        if complaint_status == "N/A"
        else complaint_status
    )

    state["resolution_type"] = (
        ""
        if resolution_type == "N/A"
        else resolution_type
    )

    state["resolution_status"] = (
        ""
        if resolution_status == "N/A"
        else resolution_status
    )

    state["resolution_reason"] = (
        ""
        if resolution_reason == "N/A"
        else resolution_reason
    )

    state["awaiting_resolution_confirmation"] = (
        stored_boolean_is_true(
            complaint.get(
                "awaiting_resolution_confirmation"
            )
        )
    )

    state["customer_resolution_confirmed"] = (
        stored_boolean_is_true(
            complaint.get(
                "customer_resolution_confirmed"
            )
        )
    )

    state["department"] = (
        ""
        if assigned_department == "N/A"
        else assigned_department
    )

    state["department_task_id"] = (
        ""
        if department_task_id == "N/A"
        else department_task_id
    )

    if complaint_description != "N/A":
        state["description"] = complaint_description

    return state


def apply_evidence_flow(
    state,
    order_id,
    customer,
    order,
    complaint,
    include_order_details=False,
    complaint_context=None,
):
    """
    Apply evidence and resolution workflow rules.
    """

    update_state_from_complaint(
        state,
        complaint,
    )

    evidence_status = normalize_status(
        complaint.get("evidence_status")
    )

    base_response = ""

    if include_order_details and complaint_context:
        base_response = build_order_response(
            complaint_context
        )

    # -----------------------------------------------------
    # Evidence required but not submitted
    # -----------------------------------------------------

    if should_request_evidence(complaint):
        friendly_message = (
            generate_customer_friendly_evidence_message(
                customer=customer,
                order=order,
                complaint=complaint,
            )
        )

        state["pending_field"] = "image_evidence"
        state["requires_hitl"] = False

        evidence_response = (
            "### 📷 Image Evidence Required\n\n"
            f"{friendly_message}"
        )

        if base_response:
            state["response"] = (
                f"{base_response}\n\n"
                f"{evidence_response}"
            )
        else:
            state["response"] = evidence_response

        logger.info(
            "Requesting image evidence. "
            "Case ID=%s, Order ID=%s, "
            "Issue Type=%s, Evidence Status=%s",
            complaint.get("case_id"),
            order_id,
            complaint.get("issue_type"),
            evidence_status,
        )

        return state

    # -----------------------------------------------------
    # Evidence waiting for review
    # -----------------------------------------------------

    if evidence_is_under_review(complaint):
        state["pending_field"] = "evidence_review"
        state["requires_hitl"] = True

        review_response = (
            build_evidence_under_review_response(
                order_id,
                complaint,
            )
        )

        if base_response:
            state["response"] = (
                f"{base_response}\n\n"
                f"{review_response}"
            )
        else:
            state["response"] = review_response

        return state

    # -----------------------------------------------------
    # Resolution confirmation pending
    # -----------------------------------------------------

    if resolution_confirmation_is_pending(complaint):
        state["pending_field"] = (
            "resolution_confirmation"
        )
        state["requires_hitl"] = False

        confirmation_response = (
            build_resolution_confirmation_response(
                order_id,
                complaint,
            )
        )

        if base_response:
            state["response"] = (
                f"{base_response}\n\n"
                f"{confirmation_response}"
            )
        else:
            state["response"] = confirmation_response

        return state

    # -----------------------------------------------------
    # Evidence approved
    # -----------------------------------------------------

    if evidence_status == "APPROVED":
        state["pending_field"] = ""
        state["requires_hitl"] = False

        approval_response = (
            build_evidence_decision_response(
                order_id,
                complaint,
            )
        )

        if base_response:
            state["response"] = (
                f"{base_response}\n\n"
                f"{approval_response}"
            )
        else:
            state["response"] = approval_response

        return state

    # -----------------------------------------------------
    # Evidence rejected
    # -----------------------------------------------------

    if evidence_status in {
        "REJECTED",
        "INVALID",
    }:
        state["pending_field"] = "image_evidence"
        state["requires_hitl"] = False

        rejection_response = (
            build_evidence_decision_response(
                order_id,
                complaint,
            )
        )

        if base_response:
            state["response"] = (
                f"{base_response}\n\n"
                f"{rejection_response}"
            )
        else:
            state["response"] = rejection_response

        return state

    # -----------------------------------------------------
    # Default status
    # -----------------------------------------------------

    state["pending_field"] = ""
    state["requires_hitl"] = False

    if base_response:
        state["response"] = base_response
    else:
        state["response"] = build_status_response(
            order_id,
            complaint,
        )

    return state


# =========================================================
# COMPLAINT AGENT
# =========================================================

def complaint_agent(state):
    """
    Complaint workflow:

    1. Ask for Order ID.
    2. Look up order and complaint.
    3. Continue existing complaint workflow.
    4. Register a complaint when none exists.
    5. Ask for image evidence when required.
    6. Wait for human evidence review.
    7. Display resolution recommendation.
    """

    logger.info(
        "========== COMPLAINT AGENT STARTED =========="
    )

    user_query = str(
        state.get("user_query", "")
    ).strip()

    pending_field = str(
        state.get("pending_field", "")
    ).strip().lower()

    stored_order_id = str(
        state.get("order_id", "")
    ).strip().upper()

    logger.info(
        "Complaint Agent input. "
        "Query=%s, Pending=%s, Order ID=%s",
        user_query,
        pending_field,
        stored_order_id,
    )

    state["intent"] = "complaint"
    state["requires_hitl"] = False
    state["review_id"] = ""

    if not state.get("sources"):
        state["sources"] = []

    # =====================================================
    # STEP 1: INITIAL COMPLAINT MESSAGE
    # =====================================================

    if not pending_field and not stored_order_id:
        state["pending_field"] = "order_id"
        state["complaint_status"] = (
            "COLLECTING_INFORMATION"
        )

        if user_query:
            state["description"] = user_query

        state["response"] = (
            "I'm sorry you're experiencing an issue with your "
            "order. I'll help you check it.\n\n"
            "Please provide your **Order ID**."
        )

        return state

    # =====================================================
    # STEP 2: CUSTOMER PROVIDES ORDER ID
    # =====================================================

    if pending_field == "order_id":
        entered_order_id = extract_order_id(
            user_query
        )

        if not entered_order_id:
            state["pending_field"] = "order_id"

            state["response"] = (
                "Please enter a valid Order ID, for example "
                "**ORD5001**."
            )

            return state

        complaint_context = lookup_complaint_data(
            entered_order_id
        )

        if complaint_context is None:
            state["order_id"] = ""
            state["pending_field"] = "order_id"

            state["response"] = (
                f"I couldn't find an order with ID "
                f"**{entered_order_id}**.\n\n"
                "Please check the Order ID and enter it again."
            )

            return state

        order = complaint_context.get("order") or {}
        customer = (
            complaint_context.get("customer") or {}
        )
        complaint = complaint_context.get("complaint")

        returned_order_id = clean_value(
            order.get("order_id")
        )

        if returned_order_id == "N/A":
            returned_order_id = entered_order_id

        state["order_id"] = returned_order_id

        order_customer_id = clean_value(
            order.get("customer_id")
        )

        logged_in_customer_id = str(
            state.get("customer_id", "")
        ).strip().upper()

        normalized_order_customer_id = (
            ""
            if order_customer_id == "N/A"
            else order_customer_id.upper()
        )

        if (
            logged_in_customer_id
            and normalized_order_customer_id
            and logged_in_customer_id
            != normalized_order_customer_id
        ):
            state["order_id"] = ""
            state["case_id"] = ""
            state["pending_field"] = "order_id"

            state["response"] = (
                "I couldn't verify this order under the currently "
                "logged-in customer account.\n\n"
                "Please check the Order ID and enter it again."
            )

            return state

        customer_id = clean_value(
            customer.get("customer_id")
        )

        if customer_id == "N/A":
            customer_id = order_customer_id

        if customer_id != "N/A":
            state["customer_id"] = customer_id

        state["sources"] = [
            "customers.csv",
            "orders.csv",
            "complaints.csv",
        ]

        # -------------------------------------------------
        # No previous complaint
        # -------------------------------------------------

        if not complaint:
            state["case_id"] = ""
            state["issue_type"] = ""
            state["description"] = ""
            state["complaint_status"] = "NOT_REGISTERED"
            state["pending_field"] = "new_complaint_issue"
            state["requires_hitl"] = False

            order_response = build_order_response(
                complaint_context
            )

            state["response"] = (
                f"{order_response}\n\n"
                "### 📝 Describe Your Issue\n\n"
                "I found your order, but no complaint is currently "
                "registered for it.\n\n"
                "Please describe the issue you are facing with the "
                "product."
            )

            return state

        # -------------------------------------------------
        # Existing complaint
        # -------------------------------------------------

        logger.info(
            "Existing complaint found. "
            "Order ID=%s, Case ID=%s, "
            "Complaint Status=%s, Evidence Status=%s",
            returned_order_id,
            complaint.get("case_id"),
            complaint.get("complaint_status"),
            complaint.get("evidence_status"),
        )

        return apply_evidence_flow(
            state=state,
            order_id=returned_order_id,
            customer=customer,
            order=order,
            complaint=complaint,
            include_order_details=True,
            complaint_context=complaint_context,
        )

    # =====================================================
    # STEP 3: CUSTOMER DESCRIBES NEW COMPLAINT
    # =====================================================

    if pending_field == "new_complaint_issue":
        issue_description = user_query.strip()

        if len(issue_description) < 10:
            state["pending_field"] = (
                "new_complaint_issue"
            )

            state["response"] = (
                "Please provide a little more detail about the "
                "issue. Explain what is damaged, missing, "
                "incorrect, delayed, or not working."
            )

            return state

        if not stored_order_id:
            state["pending_field"] = "order_id"

            state["response"] = (
                "The Order ID is missing. Please provide your "
                "**Order ID** again."
            )

            return state

        complaint_context = lookup_complaint_data(
            stored_order_id
        )

        if complaint_context is None:
            state["order_id"] = ""
            state["case_id"] = ""
            state["pending_field"] = "order_id"

            state["response"] = (
                "I couldn't reload the order information.\n\n"
                "Please provide your **Order ID** again."
            )

            return state

        order = complaint_context.get("order") or {}
        customer = (
            complaint_context.get("customer") or {}
        )
        existing_complaint = (
            complaint_context.get("complaint")
        )

        if existing_complaint:
            return apply_evidence_flow(
                state=state,
                order_id=stored_order_id,
                customer=customer,
                order=order,
                complaint=existing_complaint,
                include_order_details=False,
                complaint_context=complaint_context,
            )

        issue_type = normalize_status(
            classify_complaint_issue(
                issue_description
            )
        )

        if not issue_type:
            issue_type = "OTHER"

        customer_id = clean_value(
            customer.get("customer_id")
        )

        if customer_id == "N/A":
            customer_id = clean_value(
                order.get("customer_id")
            )

        product_id = clean_value(
            order.get("product_id")
        )

        if product_id == "N/A":
            product_id = ""

        try:
            new_complaint = (
                ComplaintRepository.create_complaint(
                    customer_id=customer_id,
                    order_id=stored_order_id,
                    product_id=product_id,
                    description=issue_description,
                    issue_type=issue_type,
                )
            )

        except Exception as exc:
            logger.exception(
                "Complaint registration failed. "
                "Order ID=%s, Error=%s",
                stored_order_id,
                exc,
            )

            state["pending_field"] = (
                "new_complaint_issue"
            )
            state["response"] = (
                "I couldn't register the complaint right now. "
                "Please try again."
            )

            return state

        case_id = str(
            new_complaint.get("case_id", "")
        ).strip()

        complaint_status = normalize_status(
            new_complaint.get(
                "complaint_status",
                "OPEN",
            )
        )

        state["case_id"] = case_id
        state["issue_type"] = issue_type
        state["description"] = issue_description
        state["complaint_status"] = complaint_status
        state["requires_hitl"] = False
        state["sources"] = [
            "customers.csv",
            "orders.csv",
            "complaints.csv",
        ]

        customer_name = clean_value(
            customer.get("customer_name")
        )

        if customer_name == "N/A":
            customer_name = "Customer"

        product_name = clean_value(
            order.get("product_name")
        )

        if product_name == "N/A":
            product_name = "your product"

        if issue_type in EVIDENCE_REQUIRED_ISSUES:
            state["pending_field"] = "image_evidence"

            friendly_message = (
                generate_customer_friendly_evidence_message(
                    customer=customer,
                    order=order,
                    complaint=new_complaint,
                )
            )

            state["response"] = (
                "### ✅ Complaint Registered Successfully\n\n"
                f"Thank you, {customer_name}. Your complaint for "
                f"**{product_name}** has been registered.\n\n"
                f"**Case ID:** {case_id}\n\n"
                f"**Order ID:** {stored_order_id}\n\n"
                f"**Issue Type:** {issue_type}\n\n"
                f"**Complaint Status:** {complaint_status}\n\n"
                "### 📷 Image Evidence Required\n\n"
                f"{friendly_message}"
            )

            return state

        state["pending_field"] = ""

        state["response"] = (
            "### ✅ Complaint Registered Successfully\n\n"
            f"Thank you, {customer_name}. Your complaint for "
            f"**{product_name}** has been registered.\n\n"
            f"**Case ID:** {case_id}\n\n"
            f"**Order ID:** {stored_order_id}\n\n"
            f"**Issue Type:** {issue_type}\n\n"
            f"**Complaint Status:** {complaint_status}\n\n"
            "Image evidence is not required for this issue. "
            "The appropriate resolution will now be determined."
        )

        return state

    # =====================================================
    # STEP 4: CUSTOMER MUST UPLOAD IMAGE
    # =====================================================

    if pending_field == "image_evidence":
        state["requires_hitl"] = False

        state["response"] = (
            "### 📷 Upload Image Evidence\n\n"
            "Please use the image uploader shown below to upload "
            "a clear image of the product and the reported issue.\n\n"
            "After submission, the image will be sent to a human "
            "customer-care reviewer."
        )

        return state

    # =====================================================
    # STEP 5: CHECK HUMAN REVIEW STATUS
    # =====================================================

    if pending_field == "evidence_review":
        if not stored_order_id:
            state["pending_field"] = "order_id"
            state["requires_hitl"] = False

            state["response"] = (
                "Please provide your Order ID so I can check "
                "the evidence-review status."
            )

            return state

        complaint_context = lookup_complaint_data(
            stored_order_id
        )

        if complaint_context is None:
            state["response"] = (
                "I couldn't reload the complaint information. "
                "Please try again."
            )

            return state

        complaint = complaint_context.get("complaint")

        if not complaint:
            state["pending_field"] = ""
            state["requires_hitl"] = False
            state["response"] = (
                "No complaint record was found for this order."
            )

            return state

        return apply_evidence_flow(
            state=state,
            order_id=stored_order_id,
            customer=(
                complaint_context.get("customer") or {}
            ),
            order=(
                complaint_context.get("order") or {}
            ),
            complaint=complaint,
        )

    # =====================================================
    # STEP 6: RESOLUTION CONFIRMATION DISPLAY
    # =====================================================

        # =====================================================
    # STEP 6: HANDLE RESOLUTION CONFIRMATION
    # =====================================================

    if pending_field == "resolution_confirmation":
        state["requires_hitl"] = False

        if not stored_order_id:
            state["pending_field"] = "order_id"

            state["response"] = (
                "The Order ID is missing. Please provide your "
                "**Order ID** again."
            )

            return state

        # Always reload the latest complaint from the database.
        complaint_context = lookup_complaint_data(
            stored_order_id
        )

        if complaint_context is None:
            state["order_id"] = ""
            state["case_id"] = ""
            state["pending_field"] = "order_id"

            state["response"] = (
                "I couldn't reload the complaint details.\n\n"
                "Please provide your **Order ID** again."
            )

            return state

        complaint = complaint_context.get(
            "complaint"
        )

        if not complaint:
            state["case_id"] = ""
            state["pending_field"] = "new_complaint_issue"
            state["complaint_status"] = "NOT_REGISTERED"

            state["response"] = (
                "No complaint was found for this order.\n\n"
                "Please describe the issue you are facing."
            )

            return state

        update_state_from_complaint(
            state,
            complaint,
        )

        case_id = str(
            complaint.get(
                "case_id",
                "",
            )
        ).strip().upper()

        resolution_type = normalize_status(
            complaint.get("resolution_type")
        )

        resolution_status = normalize_status(
            complaint.get("resolution_status")
        )

        awaiting_confirmation = (
            stored_boolean_is_true(
                complaint.get(
                    "awaiting_resolution_confirmation"
                )
            )
        )

        customer_answer = normalize_customer_answer(
            user_query
        )

        logger.info(
            "Resolution confirmation received. "
            "Case ID=%s, Order ID=%s, "
            "Resolution=%s, Status=%s, "
            "Awaiting=%s, Answer=%s",
            case_id,
            stored_order_id,
            resolution_type,
            resolution_status,
            awaiting_confirmation,
            customer_answer,
        )

        # -------------------------------------------------
        # Validate database recommendation
        # -------------------------------------------------

        if resolution_type not in VALID_RESOLUTION_TYPES:
            state["pending_field"] = ""

            state["response"] = (
                "I couldn't find a valid return, refund, or "
                "replacement recommendation for this complaint."
            )

            return state

        # This handles a Streamlit rerun after confirmation.
        if (
            resolution_status in {
                "CONFIRMED",
                "PROCESSING",
                "COMPLETED",
            }
            or stored_boolean_is_true(
                complaint.get(
                    "customer_resolution_confirmed"
                )
            )
        ):
            task_id = clean_value(
                complaint.get("department_task_id")
            )

            department = clean_value(
                complaint.get("assigned_department")
            )

            state["pending_field"] = ""
            state["awaiting_resolution_confirmation"] = False
            state["customer_resolution_confirmed"] = True

            if task_id != "N/A":
                state["department_task_id"] = task_id

            if department != "N/A":
                state["department"] = department

            state["response"] = (
                "### ✅ Resolution Already Confirmed\n\n"
                f"Your **{resolution_type.lower()}** request "
                "has already been confirmed.\n\n"
                f"**Case ID:** {case_id}\n\n"
                f"**Order ID:** {stored_order_id}\n\n"
                f"**Department:** {department}\n\n"
                f"**Task ID:** {task_id}\n\n"
                "The responsible department is processing "
                "your request."
            )

            return state

        if (
            resolution_status != "RECOMMENDED"
            or not awaiting_confirmation
        ):
            state["pending_field"] = ""

            return apply_evidence_flow(
                state=state,
                order_id=stored_order_id,
                customer=(
                    complaint_context.get("customer")
                    or {}
                ),
                order=(
                    complaint_context.get("order")
                    or {}
                ),
                complaint=complaint,
            )

        # -------------------------------------------------
        # Customer confirms the resolution
        # -------------------------------------------------

        if customer_answer in YES_RESPONSES:
            department = get_resolution_department(
                resolution_type
            )

            action = get_resolution_action(
                resolution_type
            )

            if not department:
                state["pending_field"] = (
                    "resolution_confirmation"
                )

                state["response"] = (
                    "No processing department is configured for "
                    f"the recommended {resolution_type.lower()}."
                )

                return state

            try:
                # First check for a task created during an earlier
                # partially completed request.
                department_task = (
                    get_active_department_task(
                        case_id
                    )
                )

                if department_task is None:
                    confirmed_count = (
                        ComplaintRepository.confirm_resolution(
                            case_id=case_id
                        )
                    )

                    if confirmed_count <= 0:
                        raise RuntimeError(
                            "The resolution confirmation "
                            "could not be saved."
                        )

                    department_task = (
                        DepartmentTaskRepository.create_task(
                            case_id=case_id,
                            department=department,
                            action=action,
                            resolution=resolution_type,
                            status="PENDING",
                            notes=(
                                "Customer confirmed the "
                                "recommended resolution."
                            ),
                        )
                    )

                task_id = str(
                    department_task.get(
                        "task_id",
                        "",
                    )
                ).strip().upper()

                if not task_id:
                    raise RuntimeError(
                        "The department task was not created."
                    )

                latest_complaint = (
                    ComplaintRepository.get_by_case(
                        case_id
                    )
                )

                linked_task_id = str(
                    (
                        latest_complaint
                        or {}
                    ).get(
                        "department_task_id",
                        "",
                    )
                ).strip().upper()

                # Link only if it is not already linked.
                if not linked_task_id:
                    linked_count = (
                        ComplaintRepository
                        .assign_department_task(
                            case_id=case_id,
                            department=department,
                            department_task_id=task_id,
                        )
                    )

                    if linked_count <= 0:
                        raise RuntimeError(
                            "The department task was created, "
                            "but it could not be linked to "
                            "the complaint."
                        )

                state["pending_field"] = ""
                state["complaint_status"] = (
                    "DEPARTMENT_PROCESSING"
                )
                state["resolution_type"] = resolution_type
                state["resolution_status"] = "PROCESSING"
                state[
                    "awaiting_resolution_confirmation"
                ] = False
                state[
                    "customer_resolution_confirmed"
                ] = True
                state["department"] = department
                state["department_task_id"] = task_id

                state["response"] = (
                    "### ✅ Resolution Confirmed\n\n"
                    f"Your **{resolution_type.lower()}** request "
                    "has been confirmed successfully.\n\n"
                    f"**Case ID:** {case_id}\n\n"
                    f"**Order ID:** {stored_order_id}\n\n"
                    f"**Department:** {department}\n\n"
                    f"**Task ID:** {task_id}\n\n"
                    "Your request has been forwarded to the "
                    "appropriate department for processing."
                )

                logger.info(
                    "Resolution confirmed and department task "
                    "created. Case ID=%s, Resolution=%s, "
                    "Department=%s, Task ID=%s",
                    case_id,
                    resolution_type,
                    department,
                    task_id,
                )

                return state

            except Exception as exc:
                logger.exception(
                    "Resolution confirmation failed. "
                    "Case ID=%s, Error=%s",
                    case_id,
                    exc,
                )

                # Reload because confirmation or task creation
                # may have succeeded before a later step failed.
                latest_complaint = (
                    ComplaintRepository.get_by_case(
                        case_id
                    )
                )

                if latest_complaint:
                    latest_task_id = str(
                        latest_complaint.get(
                            "department_task_id",
                            "",
                        )
                    ).strip().upper()

                    if latest_task_id:
                        state["pending_field"] = ""
                        state[
                            "awaiting_resolution_confirmation"
                        ] = False
                        state[
                            "customer_resolution_confirmed"
                        ] = True

                        state["response"] = (
                            "### ✅ Resolution Confirmed\n\n"
                            "Your request has already been sent "
                            "to the appropriate department.\n\n"
                            f"**Task ID:** {latest_task_id}"
                        )

                        return state

                state["pending_field"] = (
                    "resolution_confirmation"
                )

                state["response"] = (
                    "I couldn't complete the resolution "
                    "confirmation right now. Please try again."
                )

                return state

        # -------------------------------------------------
        # Customer declines the resolution
        # -------------------------------------------------

        if customer_answer in NO_RESPONSES:
            try:
                declined_count = (
                    ComplaintRepository.decline_resolution(
                        case_id=case_id
                    )
                )

                if declined_count <= 0:
                    raise RuntimeError(
                        "The response could not be saved."
                    )

                state["pending_field"] = ""
                state["complaint_status"] = (
                    "AWAITING_CASE_MANAGER"
                )
                state["resolution_status"] = "DECLINED"
                state[
                    "awaiting_resolution_confirmation"
                ] = False
                state[
                    "customer_resolution_confirmed"
                ] = False
                state["department"] = ""
                state["department_task_id"] = ""

                state["response"] = (
                    "### Resolution Declined\n\n"
                    f"The recommended "
                    f"**{resolution_type.lower()}** has not "
                    "been processed.\n\n"
                    f"**Case ID:** {case_id}\n\n"
                    f"**Order ID:** {stored_order_id}\n\n"
                    "Your complaint has been forwarded to the "
                    "Case Manager for further review."
                )

                logger.info(
                    "Customer declined resolution. "
                    "Case ID=%s, Resolution=%s",
                    case_id,
                    resolution_type,
                )

                return state

            except Exception as exc:
                logger.exception(
                    "Resolution decline failed. "
                    "Case ID=%s, Error=%s",
                    case_id,
                    exc,
                )

                state["pending_field"] = (
                    "resolution_confirmation"
                )

                state["response"] = (
                    "I couldn't save your response right now. "
                    "Please try again."
                )

                return state

        # -------------------------------------------------
        # Invalid answer
        # -------------------------------------------------

        state["pending_field"] = (
            "resolution_confirmation"
        )

        state["response"] = (
            f"A **{resolution_type.lower()}** has been "
            "recommended for your complaint.\n\n"
            "Please reply **Yes** to proceed or "
            "**No** to decline."
        )

        return state

    # =====================================================
    # STEP 7: CONTINUED COMPLAINT CONVERSATION
    # =====================================================

    if stored_order_id:
        complaint_context = lookup_complaint_data(
            stored_order_id
        )

        if complaint_context is None:
            state["order_id"] = ""
            state["case_id"] = ""
            state["pending_field"] = "order_id"

            state["response"] = (
                f"I couldn't reload the details for order "
                f"**{stored_order_id}**.\n\n"
                "Please provide the Order ID again."
            )

            return state

        complaint = complaint_context.get("complaint")

        if not complaint:
            state["case_id"] = ""
            state["complaint_status"] = "NOT_REGISTERED"
            state["pending_field"] = "new_complaint_issue"
            state["requires_hitl"] = False

            state["response"] = (
                "I found your order, but no complaint is "
                "registered for it.\n\n"
                "Please describe the issue you are facing with "
                "the product."
            )

            return state

        return apply_evidence_flow(
            state=state,
            order_id=stored_order_id,
            customer=(
                complaint_context.get("customer") or {}
            ),
            order=(
                complaint_context.get("order") or {}
            ),
            complaint=complaint,
        )

    # =====================================================
    # FINAL FALLBACK
    # =====================================================

    state["pending_field"] = "order_id"
    state["complaint_status"] = (
        "COLLECTING_INFORMATION"
    )

    state["response"] = (
        "I can help you with your complaint.\n\n"
        "Please provide your **Order ID**."
    )

    return state