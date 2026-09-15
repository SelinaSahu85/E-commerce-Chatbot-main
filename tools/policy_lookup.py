"""
Policy Lookup Tool

Determines whether a complaint is eligible for:
    - RETURN
    - REFUND
    - REPLACEMENT
    - Manual review

This tool only recommends a resolution.
It does not create department tasks or update CSV files.
"""

from typing import Any, Dict

from utils.logger import logger


# Issue types after normalization.
# Example:
# "Damaged Product" becomes "damaged_product".

DAMAGED_PRODUCT_ISSUES = {
    "damaged_product",
    "product_damaged",
    "broken_product",
    "defective_product",
}

WRONG_ITEM_ISSUES = {
    "wrong_item",
    "incorrect_item",
    "different_item_received",
}

MISSING_ITEM_ISSUES = {
    "missing_item",
    "item_missing",
    "product_not_received",
    "order_not_received",
}

RETURN_ISSUES = {
    "return_request",
    "unwanted_product",
    "changed_mind",
    "size_issue",
    "size_mismatch",
}

REFUND_ISSUES = {
    "refund_request",
    "duplicate_payment",
    "payment_failed_amount_debited",
    "cancelled_order_refund",
}

MANUAL_REVIEW_ISSUES = {
    "fraud",
    "suspected_fraud",
    "high_value_claim",
    "policy_exception",
}


def check_resolution_policy(
    issue_type: str,
    evidence_status: str = "",
    replacement_available: bool = True,
) -> Dict[str, Any]:
    """
    Recommend a resolution based on complaint type, evidence status,
    and replacement availability.

    Args:
        issue_type:
            Complaint category returned by the complaint classifier.

        evidence_status:
            Evidence review status, such as:
                APPROVED
                REJECTED
                PENDING
                NOT_REQUIRED
                ""

        replacement_available:
            True when replacement stock is available.
            False when replacement is unavailable.

    Returns:
        A dictionary containing:
            eligible
            resolution_type
            reason
            requires_manual_review
    """

    try:
        normalized_issue = normalize_issue_type(issue_type)
        normalized_evidence = normalize_evidence_status(
            evidence_status
        )
        replacement_is_available = convert_to_bool(
            replacement_available
        )

        logger.info(
            "Policy lookup started | issue_type=%s | "
            "evidence_status=%s | replacement_available=%s",
            normalized_issue,
            normalized_evidence,
            replacement_is_available,
        )

        if not normalized_issue:
            logger.warning(
                "Policy lookup failed because issue_type is empty."
            )

            return build_manual_review_response(
                reason="Complaint issue type is missing."
            )

        # ----------------------------------------------------------
        # Damaged or defective product
        # ----------------------------------------------------------

        if normalized_issue in DAMAGED_PRODUCT_ISSUES:
            return evaluate_evidence_based_replacement(
                issue_label="damaged product",
                evidence_status=normalized_evidence,
                replacement_available=replacement_is_available,
            )

        # ----------------------------------------------------------
        # Wrong or incorrect item
        # ----------------------------------------------------------

        if normalized_issue in WRONG_ITEM_ISSUES:
            return evaluate_evidence_based_replacement(
                issue_label="wrong item",
                evidence_status=normalized_evidence,
                replacement_available=replacement_is_available,
            )

        # ----------------------------------------------------------
        # Missing or undelivered item
        # ----------------------------------------------------------

        if normalized_issue in MISSING_ITEM_ISSUES:
            logger.info(
                "Missing item policy matched. "
                "Refund is being recommended."
            )

            return build_eligible_response(
                resolution_type="REFUND",
                reason=(
                    "The item is reported as missing or not received. "
                    "A refund is recommended."
                ),
            )

        # ----------------------------------------------------------
        # Customer return request
        # ----------------------------------------------------------

        if normalized_issue in RETURN_ISSUES:
            logger.info(
                "Return policy matched. "
                "Return is being recommended."
            )

            return build_eligible_response(
                resolution_type="RETURN",
                reason=(
                    "The complaint is eligible for a return under "
                    "the configured return policy."
                ),
            )

        # ----------------------------------------------------------
        # Direct refund request or payment problem
        # ----------------------------------------------------------

        if normalized_issue in REFUND_ISSUES:
            logger.info(
                "Refund policy matched. "
                "Refund is being recommended."
            )

            return build_eligible_response(
                resolution_type="REFUND",
                reason=(
                    "The complaint is eligible for a refund under "
                    "the configured refund policy."
                ),
            )

        # ----------------------------------------------------------
        # Cases that must be checked by the Case Manager
        # ----------------------------------------------------------

        if normalized_issue in MANUAL_REVIEW_ISSUES:
            logger.info(
                "Manual review policy matched for issue_type=%s",
                normalized_issue,
            )

            return build_manual_review_response(
                reason=(
                    "This complaint requires review by the "
                    "Case Manager."
                )
            )

        # ----------------------------------------------------------
        # Unknown complaint category
        # ----------------------------------------------------------

        logger.warning(
            "No policy configured for issue_type=%s",
            normalized_issue,
        )

        return build_manual_review_response(
            reason=(
                f"No automatic resolution policy is configured for "
                f"issue type '{normalized_issue}'."
            )
        )

    except Exception as exc:
        logger.exception(
            "Unexpected policy lookup error: %s",
            exc,
        )

        return build_manual_review_response(
            reason=(
                "An unexpected error occurred while checking "
                "the complaint policy."
            )
        )


def evaluate_evidence_based_replacement(
    issue_label: str,
    evidence_status: str,
    replacement_available: bool,
) -> Dict[str, Any]:
    """
    Evaluate damaged-product and wrong-item complaints.

    Approved evidence is mandatory. If replacement stock is
    unavailable, refund is recommended instead.
    """

    if evidence_status in {
        "",
        "NOT_UPLOADED",
        "REQUIRED",
    }:
        logger.info(
            "Evidence has not been uploaded for issue=%s",
            issue_label,
        )

        return build_not_eligible_response(
            reason=(
                f"Evidence is required for the {issue_label} "
                "complaint before a resolution can be recommended."
            )
        )

    if evidence_status in {
        "UPLOADED",
        "PENDING",
        "PENDING_REVIEW",
        "UNDER_REVIEW",
    }:
        logger.info(
            "Evidence is waiting for review for issue=%s",
            issue_label,
        )

        return build_not_eligible_response(
            reason=(
                "The submitted evidence is waiting for human review."
            )
        )

    if evidence_status in {
        "REJECTED",
        "DECLINED",
        "INVALID",
    }:
        logger.info(
            "Evidence was rejected for issue=%s",
            issue_label,
        )

        return build_not_eligible_response(
            reason=(
                f"The evidence submitted for the {issue_label} "
                "complaint was not approved."
            )
        )

    if evidence_status != "APPROVED":
        logger.warning(
            "Unknown evidence status=%s for issue=%s",
            evidence_status,
            issue_label,
        )

        return build_manual_review_response(
            reason=(
                f"Evidence status '{evidence_status}' is not "
                "recognized and requires manual review."
            )
        )

    if replacement_available:
        logger.info(
            "Evidence approved and replacement available "
            "for issue=%s",
            issue_label,
        )

        return build_eligible_response(
            resolution_type="REPLACEMENT",
            reason=(
                f"The evidence for the {issue_label} complaint "
                "has been approved and replacement stock is available."
            ),
        )

    logger.info(
        "Evidence approved but replacement unavailable "
        "for issue=%s",
        issue_label,
    )

    return build_eligible_response(
        resolution_type="REFUND",
        reason=(
            f"The evidence for the {issue_label} complaint has "
            "been approved, but replacement stock is unavailable. "
            "A refund is recommended."
        ),
    )


def build_eligible_response(
    resolution_type: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Build a standard eligible policy response.
    """

    return {
        "eligible": True,
        "resolution_type": resolution_type,
        "reason": reason,
        "requires_manual_review": False,
    }


def build_not_eligible_response(
    reason: str,
) -> Dict[str, Any]:
    """
    Build a response when the case cannot yet receive a resolution.

    This does not send the case to manual review automatically.
    For example, evidence may still be pending.
    """

    return {
        "eligible": False,
        "resolution_type": None,
        "reason": reason,
        "requires_manual_review": False,
    }


def build_manual_review_response(
    reason: str,
) -> Dict[str, Any]:
    """
    Build a standard manual-review policy response.
    """

    return {
        "eligible": False,
        "resolution_type": None,
        "reason": reason,
        "requires_manual_review": True,
    }


def normalize_issue_type(
    issue_type: Any,
) -> str:
    """
    Normalize classifier output.

    Examples:
        "Damaged Product" -> "damaged_product"
        "WRONG-ITEM"      -> "wrong_item"
        " refund_request " -> "refund_request"
    """

    if issue_type is None:
        return ""

    normalized = str(issue_type).strip().lower()
    normalized = normalized.replace("-", "_")
    normalized = normalized.replace("/", "_")
    normalized = "_".join(normalized.split())

    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    return normalized.strip("_")


def normalize_evidence_status(
    evidence_status: Any,
) -> str:
    """
    Normalize evidence status.

    Examples:
        "approved"       -> "APPROVED"
        "Pending Review" -> "PENDING_REVIEW"
    """

    if evidence_status is None:
        return ""

    normalized = str(evidence_status).strip().upper()
    normalized = normalized.replace("-", "_")
    normalized = "_".join(normalized.split())

    while "__" in normalized:
        normalized = normalized.replace("__", "_")

    return normalized.strip("_")


def convert_to_bool(
    value: Any,
) -> bool:
    """
    Convert common values into Boolean values.
    """

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, int):
        return value != 0

    normalized = str(value).strip().lower()

    if normalized in {
        "true",
        "1",
        "yes",
        "y",
        "available",
        "in_stock",
    }:
        return True

    if normalized in {
        "false",
        "0",
        "no",
        "n",
        "unavailable",
        "out_of_stock",
        "",
    }:
        return False

    logger.warning(
        "Unrecognized Boolean value=%s. Defaulting to False.",
        value,
    )

    return False
