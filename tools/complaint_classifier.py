import os
import re

from utils.logger import logger


ALLOWED_ISSUE_TYPES = {
    "DAMAGED_PRODUCT",
    "DEFECTIVE_PRODUCT",
    "WRONG_ITEM",
    "MISSING_ITEM",
    "DELIVERY_DELAY",
    "PAYMENT_ISSUE",
    "RETURN_REQUEST",
    "REFUND_REQUEST",
    "OTHER",
}


def _clean_issue_type(value):
    """
    Normalize the classifier result.
    """

    issue_type = str(
        value or ""
    ).strip().upper()

    issue_type = issue_type.replace(
        " ",
        "_",
    )

    issue_type = re.sub(
        r"[^A-Z_]",
        "",
        issue_type,
    )

    return issue_type


def _rule_based_classification(description):
    """
    Rule-based fallback classifier.

    This is used when:
    - Gemini is unavailable
    - the API key is missing
    - the network request fails
    - the LLM returns an invalid category
    """

    normalized_description = str(
        description or ""
    ).strip().lower()

    if not normalized_description:
        return "OTHER"

    damaged_keywords = [
        "damaged",
        "broken",
        "cracked",
        "shattered",
        "scratched",
        "scratch",
        "dented",
        "dent",
        "torn",
        "leaking",
        "physical damage",
    ]

    defective_keywords = [
        "defective",
        "not working",
        "does not work",
        "stopped working",
        "faulty",
        "malfunction",
        "not turning on",
        "not switching on",
        "overheating",
    ]

    wrong_item_keywords = [
        "wrong item",
        "wrong product",
        "different product",
        "incorrect product",
        "incorrect item",
        "wrong color",
        "wrong colour",
        "wrong size",
    ]

    missing_item_keywords = [
        "missing item",
        "item is missing",
        "item missing",
        "missing product",
        "empty package",
        "package was empty",
        "accessory missing",
        "part is missing",
    ]

    delivery_delay_keywords = [
        "delivery delayed",
        "delayed delivery",
        "late delivery",
        "not delivered",
        "not arrived",
        "delivery is late",
        "package is late",
        "order is late",
    ]

    payment_issue_keywords = [
        "payment failed",
        "charged twice",
        "duplicate charge",
        "money deducted",
        "amount deducted",
        "billing problem",
        "billing issue",
        "payment issue",
    ]

    return_request_keywords = [
        "want to return",
        "return this product",
        "return the product",
        "return request",
        "send it back",
    ]

    refund_request_keywords = [
        "want a refund",
        "need a refund",
        "refund request",
        "money back",
        "refund my money",
    ]

    if any(
        keyword in normalized_description
        for keyword in damaged_keywords
    ):
        return "DAMAGED_PRODUCT"

    if any(
        keyword in normalized_description
        for keyword in defective_keywords
    ):
        return "DEFECTIVE_PRODUCT"

    if any(
        keyword in normalized_description
        for keyword in wrong_item_keywords
    ):
        return "WRONG_ITEM"

    if any(
        keyword in normalized_description
        for keyword in missing_item_keywords
    ):
        return "MISSING_ITEM"

    if any(
        keyword in normalized_description
        for keyword in delivery_delay_keywords
    ):
        return "DELIVERY_DELAY"

    if any(
        keyword in normalized_description
        for keyword in payment_issue_keywords
    ):
        return "PAYMENT_ISSUE"

    if any(
        keyword in normalized_description
        for keyword in return_request_keywords
    ):
        return "RETURN_REQUEST"

    if any(
        keyword in normalized_description
        for keyword in refund_request_keywords
    ):
        return "REFUND_REQUEST"

    return "OTHER"


def classify_complaint_issue(description):
    """
    Classify a complaint description into one controlled issue type.

    Returns one of:

    DAMAGED_PRODUCT
    DEFECTIVE_PRODUCT
    WRONG_ITEM
    MISSING_ITEM
    DELIVERY_DELAY
    PAYMENT_ISSUE
    RETURN_REQUEST
    REFUND_REQUEST
    OTHER
    """

    normalized_description = str(
        description or ""
    ).strip()

    if not normalized_description:
        logger.warning(
            "Complaint classifier received an empty description."
        )

        return "OTHER"

    logger.info(
        "Complaint issue classification started. "
        "Description=%s",
        normalized_description,
    )

    api_key = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if not api_key:
        logger.warning(
            "GEMINI_API_KEY is not configured. "
            "Using rule-based complaint classification."
        )

        issue_type = _rule_based_classification(
            normalized_description
        )

        logger.info(
            "Rule-based issue classification completed. "
            "Issue Type=%s",
            issue_type,
        )

        return issue_type

    try:
        from langchain_google_genai import (
            ChatGoogleGenerativeAI,
        )

        model_name = os.getenv(
            "GEMINI_MODEL",
            "gemini-2.0-flash",
        ).strip()

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key
        )

        prompt = f"""
You are an e-commerce complaint classification system.

Classify the customer complaint into exactly one category:

DAMAGED_PRODUCT
DEFECTIVE_PRODUCT
WRONG_ITEM
MISSING_ITEM
DELIVERY_DELAY
PAYMENT_ISSUE
RETURN_REQUEST
REFUND_REQUEST
OTHER

Category definitions:

DAMAGED_PRODUCT:
The product arrived cracked, broken, scratched, dented, torn,
leaking, shattered, or physically damaged.

DEFECTIVE_PRODUCT:
The product has a functional problem, is faulty, does not work,
stopped working, overheats, or does not turn on.

WRONG_ITEM:
The customer received a different product, color, size, model,
or item from what was ordered.

MISSING_ITEM:
The ordered item, product part, accessory, or package content
is missing.

DELIVERY_DELAY:
The order has not arrived within the expected delivery time.

PAYMENT_ISSUE:
The complaint concerns payment failure, duplicate charge,
billing, or money deducted incorrectly.

RETURN_REQUEST:
The customer wants to return the product.

REFUND_REQUEST:
The customer explicitly requests money back or a refund.

OTHER:
The complaint does not match any category above.

Customer complaint:
{normalized_description}

Return only one category name.
Do not provide an explanation.
"""

        llm_result = llm.invoke(
            prompt
        )

        raw_result = getattr(
            llm_result,
            "content",
            llm_result,
        )

        issue_type = _clean_issue_type(
            raw_result
        )

        logger.info(
            "Raw LLM complaint classification: %s",
            raw_result,
        )

        if issue_type in ALLOWED_ISSUE_TYPES:
            logger.info(
                "LLM complaint classification completed. "
                "Issue Type=%s",
                issue_type,
            )

            return issue_type

        logger.warning(
            "LLM returned an unsupported issue type: %s. "
            "Using rule-based fallback.",
            issue_type,
        )

    except ImportError:
        logger.exception(
            "langchain-google-genai is not installed. "
            "Using rule-based complaint classification."
        )

    except Exception as exc:
        logger.exception(
            "LLM complaint classification failed: %s",
            exc,
        )

    fallback_issue_type = _rule_based_classification(
        normalized_description
    )

    logger.info(
        "Fallback complaint classification completed. "
        "Issue Type=%s",
        fallback_issue_type,
    )

    return fallback_issue_type