"""
Resolution Agent

Purpose:
    Decide the recommended complaint resolution after the complaint
    has been classified and any required evidence has been approved.

Possible outcomes:
    - RETURN
    - REFUND
    - REPLACEMENT
    - MANUAL_REVIEW_REQUIRED
    - NOT_ELIGIBLE

Important:
    This agent DOES NOT create a department task.

    Department tasks are only created later when:
        1. A resolution is recommended.
        2. The customer confirms the resolution.
        3. complaint_agent calls create_department_task().
"""

from typing import Any, Dict

from tools.policy_lookup import check_resolution_policy
from utils.logger import logger


# ----------------------------------------------------------------------
# Resolution Agent
# ----------------------------------------------------------------------

def resolution_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Determine the recommended resolution for a complaint.

    Expected state fields:
        issue_type
        evidence_required
        evidence_status
        replacement_available

    Adds/updates:
        resolution_type
        resolution_status
        awaiting_resolution_confirmation
        customer_resolution_confirmed
        response

    Args:
        state:
            Current complaint/chat state.

    Returns:
        Updated state dictionary.
    """

    logger.info("=" * 60)
    logger.info("RESOLUTION AGENT STARTED")
    logger.info("=" * 60)

    try:
        # --------------------------------------------------------------
        # 1. Read complaint information
        # --------------------------------------------------------------

        case_id = _clean_value(state.get("case_id"))
        order_id = _clean_value(state.get("order_id"))
        issue_type = _clean_value(state.get("issue_type"))

        evidence_required = _to_bool(
            state.get("evidence_required", False)
        )

        evidence_status = _clean_value(
            state.get("evidence_status")
        ).upper()

        replacement_available = _to_bool(
            state.get("replacement_available", True)
        )

        logger.info(
            "Resolution input | "
            "case_id=%s | "
            "order_id=%s | "
            "issue_type=%s | "
            "evidence_required=%s | "
            "evidence_status=%s | "
            "replacement_available=%s",
            case_id,
            order_id,
            issue_type,
            evidence_required,
            evidence_status,
            replacement_available,
        )

        # --------------------------------------------------------------
        # 2. Validate issue type
        # --------------------------------------------------------------

        if not issue_type:
            logger.warning(
                "Resolution cannot continue because issue_type is missing."
            )

            return {
                **state,
                "resolution_type": None,
                "resolution_status": "MANUAL_REVIEW_REQUIRED",
                "awaiting_resolution_confirmation": False,
                "customer_resolution_confirmed": False,
                "response": (
                    "I could not determine the appropriate resolution "
                    "because the complaint type is unavailable. "
                    "The case requires additional review."
                ),
            }

        # --------------------------------------------------------------
        # 3. Validate evidence before policy evaluation
        # --------------------------------------------------------------

        if evidence_required:
            if not evidence_status:
                logger.info(
                    "Evidence is required but has not been reviewed."
                )

                return {
                    **state,
                    "resolution_type": None,
                    "resolution_status": "WAITING_FOR_EVIDENCE",
                    "awaiting_resolution_confirmation": False,
                    "customer_resolution_confirmed": False,
                    "response": (
                        "Evidence is required before a resolution can "
                        "be recommended. Please upload the requested "
                        "evidence."
                    ),
                }

            if evidence_status in {
                "PENDING",
                "PENDING_REVIEW",
                "UNDER_REVIEW",
                "UPLOADED",
            }:
                logger.info(
                    "Evidence is currently awaiting human review."
                )

                return {
                    **state,
                    "resolution_type": None,
                    "resolution_status": "WAITING_FOR_EVIDENCE_REVIEW",
                    "awaiting_resolution_confirmation": False,
                    "customer_resolution_confirmed": False,
                    "response": (
                        "Your evidence has been received and is currently "
                        "awaiting review. A resolution will be recommended "
                        "after the evidence is approved."
                    ),
                }

            if evidence_status in {
                "REJECTED",
                "DECLINED",
            }:
                logger.info(
                    "Resolution stopped because evidence was rejected."
                )

                return {
                    **state,
                    "resolution_type": None,
                    "resolution_status": "EVIDENCE_REJECTED",
                    "awaiting_resolution_confirmation": False,
                    "customer_resolution_confirmed": False,
                    "response": (
                        "The submitted evidence was not approved. "
                        "Please provide valid evidence so that the "
                        "complaint can be reviewed again."
                    ),
                }

            if evidence_status != "APPROVED":
                logger.warning(
                    "Unexpected evidence status received: %s",
                    evidence_status,
                )

                return {
                    **state,
                    "resolution_type": None,
                    "resolution_status": "MANUAL_REVIEW_REQUIRED",
                    "awaiting_resolution_confirmation": False,
                    "customer_resolution_confirmed": False,
                    "response": (
                        "The evidence status requires additional review "
                        "before a resolution can be recommended."
                    ),
                }

        # --------------------------------------------------------------
        # 4. Call policy lookup
        # --------------------------------------------------------------

        logger.info(
            "Calling resolution policy for issue_type=%s",
            issue_type,
        )

        policy_result = check_resolution_policy(
            issue_type=issue_type,
            evidence_status=evidence_status,
            replacement_available=replacement_available,
        )

        logger.info(
            "Policy result received: %s",
            policy_result,
        )

        # --------------------------------------------------------------
        # 5. Validate policy response
        # --------------------------------------------------------------

        if not isinstance(policy_result, dict):
            logger.error(
                "Invalid policy response. Expected dict, received %s",
                type(policy_result).__name__,
            )

            return {
                **state,
                "resolution_type": None,
                "resolution_status": "MANUAL_REVIEW_REQUIRED",
                "awaiting_resolution_confirmation": False,
                "customer_resolution_confirmed": False,
                "response": (
                    "The complaint could not be resolved automatically. "
                    "The case requires manual review."
                ),
            }

        eligible = bool(
            policy_result.get("eligible", False)
        )

        requires_manual_review = bool(
            policy_result.get(
                "requires_manual_review",
                False,
            )
        )

        resolution_type = _clean_value(
            policy_result.get("resolution_type")
        ).upper()

        reason = _clean_value(
            policy_result.get("reason")
        )

        # --------------------------------------------------------------
        # 6. Manual review
        # --------------------------------------------------------------

        if requires_manual_review:
            logger.info(
                "Case requires manual review | case_id=%s",
                case_id,
            )

            return {
                **state,
                "resolution_type": None,
                "resolution_status": "MANUAL_REVIEW_REQUIRED",
                "resolution_reason": reason,
                "awaiting_resolution_confirmation": False,
                "customer_resolution_confirmed": False,
                "case_status": "MANUAL_REVIEW_REQUIRED",
                "response": (
                    "Your complaint requires additional review before "
                    "a resolution can be provided. The case has been "
                    "forwarded to the Case Manager for review."
                ),
            }

        # --------------------------------------------------------------
        # 7. Not eligible
        # --------------------------------------------------------------

        if not eligible:
            logger.info(
                "Complaint is not eligible for automatic resolution | "
                "case_id=%s | reason=%s",
                case_id,
                reason,
            )

            message = (
                reason
                if reason
                else (
                    "The complaint is not currently eligible for "
                    "an automatic return, refund, or replacement."
                )
            )

            return {
                **state,
                "resolution_type": None,
                "resolution_status": "NOT_ELIGIBLE",
                "resolution_reason": reason,
                "awaiting_resolution_confirmation": False,
                "customer_resolution_confirmed": False,
                "response": message,
            }

        # --------------------------------------------------------------
        # 8. Validate recommended resolution
        # --------------------------------------------------------------

        valid_resolutions = {
            "RETURN",
            "REFUND",
            "REPLACEMENT",
        }

        if resolution_type not in valid_resolutions:
            logger.error(
                "Policy returned invalid resolution_type=%s",
                resolution_type,
            )

            return {
                **state,
                "resolution_type": None,
                "resolution_status": "MANUAL_REVIEW_REQUIRED",
                "resolution_reason": reason,
                "awaiting_resolution_confirmation": False,
                "customer_resolution_confirmed": False,
                "case_status": "MANUAL_REVIEW_REQUIRED",
                "response": (
                    "The recommended resolution could not be determined "
                    "automatically. The case requires manual review."
                ),
            }

        # --------------------------------------------------------------
        # 9. Resolution successfully recommended
        # --------------------------------------------------------------

        confirmation_message = _get_confirmation_message(
            resolution_type=resolution_type,
            evidence_required=evidence_required,
        )

        logger.info(
            "Resolution successfully recommended | "
            "case_id=%s | "
            "resolution_type=%s",
            case_id,
            resolution_type,
        )

        logger.info(
            "Waiting for customer confirmation."
        )

        return {
            **state,
            "resolution_type": resolution_type,
            "resolution_status": "RECOMMENDED",
            "resolution_reason": reason,
            "awaiting_resolution_confirmation": True,
            "customer_resolution_confirmed": False,
            "response": confirmation_message,
        }

    except Exception as exc:
        logger.exception(
            "Unexpected error inside resolution_agent: %s",
            exc,
        )

        return {
            **state,
            "resolution_type": None,
            "resolution_status": "ERROR",
            "awaiting_resolution_confirmation": False,
            "customer_resolution_confirmed": False,
            "response": (
                "An error occurred while determining the resolution. "
                "The complaint has not been sent to any department."
            ),
        }


# ----------------------------------------------------------------------
# Confirmation Message
# ----------------------------------------------------------------------

def _get_confirmation_message(
    resolution_type: str,
    evidence_required: bool = False,
) -> str:
    """
    Generate the customer confirmation message for the
    recommended resolution.
    """

    if resolution_type == "REPLACEMENT":
        if evidence_required:
            return (
                "Your evidence has been approved. Based on the complaint "
                "details and applicable policy, your order is eligible "
                "for a replacement. Would you like to proceed with the "
                "replacement?"
            )

        return (
            "Based on the complaint details and applicable policy, "
            "your order is eligible for a replacement. "
            "Would you like to proceed with the replacement?"
        )

    if resolution_type == "REFUND":
        if evidence_required:
            return (
                "Your evidence has been approved. Based on the complaint "
                "details and applicable policy, your order is eligible "
                "for a refund. Would you like to proceed with the refund?"
            )

        return (
            "Based on the complaint details and applicable policy, "
            "your order is eligible for a refund. "
            "Would you like to proceed with the refund?"
        )

    if resolution_type == "RETURN":
        if evidence_required:
            return (
                "Your evidence has been approved. Based on the complaint "
                "details and applicable policy, your order is eligible "
                "for a return. Would you like to proceed with the return?"
            )

        return (
            "Based on the complaint details and applicable policy, "
            "your order is eligible for a return. "
            "Would you like to proceed with the return?"
        )

    return (
        "A resolution has been recommended for your complaint. "
        "Would you like to proceed?"
    )


# ----------------------------------------------------------------------
# Utility Functions
# ----------------------------------------------------------------------

def _clean_value(value: Any) -> str:
    """
    Convert a value to a clean string.
    """

    if value is None:
        return ""

    return str(value).strip()


def _to_bool(value: Any) -> bool:
    """
    Safely convert common boolean representations.

    Examples:
        True        -> True
        "true"      -> True
        "YES"       -> True
        "1"         -> True
        False       -> False
        "false"     -> False
        "NO"        -> False
    """

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    normalized = str(value).strip().lower()

    return normalized in {
        "true",
        "1",
        "yes",
        "y",
    }