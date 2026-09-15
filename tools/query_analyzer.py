import json
import os
import re

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from config.setting import GEMINI_MODEL
from prompts.query_analysis_prompt import QUERY_ANALYSIS_PROMPT
from tools.guardrails import check_guardrails
from utils.helpers import extract_llm_text
from utils.logger import logger


load_dotenv()


ALLOWED_INTENTS = {
    "enquiry",
    "complaint",
}

ALLOWED_SAFETY_RESULTS = {
    "SAFE",
    "HITL",
}


COMPLAINT_KEYWORDS = [
    "damaged",
    "broken",
    "cracked",
    "refund not received",
    "missing",
    "missing item",
    "wrong item",
    "wrong product",
    "late delivery",
    "delayed order",
    "not delivered",
    "complaint",
    "issue",
    "problem",
    "defective",
    "received damaged",
    "cancelled order",
    "cancellation issue",
    "screen cracked",
    "replacement",
    "not working",
]


llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    google_api_key=os.getenv("GOOGLE_API_KEY"),
)


def _extract_json(content):
    """
    Extract and parse a JSON object from the LLM response.
    """

    cleaned_content = str(
        content or ""
    ).strip()

    cleaned_content = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned_content,
        flags=re.IGNORECASE,
    )

    cleaned_content = re.sub(
        r"\s*```$",
        "",
        cleaned_content,
    )

    json_match = re.search(
        r"\{.*\}",
        cleaned_content,
        flags=re.DOTALL,
    )

    if not json_match:
        raise ValueError(
            "The query analyzer did not return a JSON object."
        )

    return json.loads(
        json_match.group(0)
    )


def _fallback_intent(query):
    """
    Classify intent using deterministic keywords if the LLM fails.
    """

    query_lower = str(
        query or ""
    ).strip().lower()

    if any(
        keyword in query_lower
        for keyword in COMPLAINT_KEYWORDS
    ):
        logger.info(
            "Fallback intent classification: complaint"
        )

        return "complaint"

    logger.info(
        "Fallback intent classification: enquiry"
    )

    return "enquiry"


def _build_result(
    intent,
    is_safe,
    safety_reason="",
    source="llm",
):
    """
    Return a consistent query-analysis result.
    """

    normalized_intent = str(
        intent or ""
    ).strip().lower()

    if normalized_intent not in ALLOWED_INTENTS:
        normalized_intent = "enquiry"

    return {
        "intent": normalized_intent,
        "is_safe": bool(is_safe),
        "safety_reason": str(
            safety_reason or ""
        ).strip(),
        "analysis_source": source,
    }


def analyze_query(query):
    """
    Analyze intent and safety using:

    1. Deterministic guardrails
    2. One LLM call for intent and safety

    Returns:

    {
        "intent": "enquiry",
        "is_safe": True,
        "safety_reason": "",
        "analysis_source": "llm"
    }
    """

    normalized_query = str(
        query or ""
    ).strip()

    if not normalized_query:
        return _build_result(
            intent="enquiry",
            is_safe=False,
            safety_reason="The customer query is empty.",
            source="validation",
        )

    logger.info(
        "Analyzing query for intent and safety: %s",
        normalized_query,
    )

    # =====================================================
    # DETERMINISTIC GUARDRAILS
    # =====================================================

    try:
        guard_result = check_guardrails(
            normalized_query
        )

    except Exception as exc:
        logger.exception(
            "Guardrail check failed: %s",
            exc,
        )

        guard_result = {
            "blocked": False,
            "reason": "",
        }

    if guard_result.get(
        "blocked",
        False,
    ):
        intent = _fallback_intent(
            normalized_query
        )

        safety_reason = str(
            guard_result.get(
                "reason",
                "The request requires human review.",
            )
        ).strip()

        logger.warning(
            "Query blocked by guardrails. "
            "Intent=%s, Reason=%s",
            intent,
            safety_reason,
        )

        return _build_result(
            intent=intent,
            is_safe=False,
            safety_reason=safety_reason,
            source="guardrails",
        )

    # =====================================================
    # ONE LLM CALL FOR INTENT AND SAFETY
    # =====================================================

    formatted_prompt = (
        QUERY_ANALYSIS_PROMPT.format(
            query=normalized_query
        )
    )

    try:
        response = llm.invoke(
            formatted_prompt
        )

        content = extract_llm_text(
            response
        )

        logger.info(
            "Raw combined analysis response: %s",
            content,
        )

        parsed_result = _extract_json(
            content
        )

        intent = str(
            parsed_result.get(
                "intent",
                "",
            )
        ).strip().lower()

        safety = str(
            parsed_result.get(
                "safety",
                "",
            )
        ).strip().upper()

        reason = str(
            parsed_result.get(
                "reason",
                "",
            )
        ).strip()

        if intent not in ALLOWED_INTENTS:
            logger.warning(
                "Invalid intent returned by LLM: %s",
                intent,
            )

            intent = _fallback_intent(
                normalized_query
            )

        if safety not in ALLOWED_SAFETY_RESULTS:
            raise ValueError(
                f"Invalid safety result returned: {safety}"
            )

        is_safe = safety == "SAFE"

        if is_safe:
            reason = ""

        result = _build_result(
            intent=intent,
            is_safe=is_safe,
            safety_reason=reason,
            source="llm",
        )

        logger.info(
            "Query analysis completed. "
            "Intent=%s, Safe=%s, Source=%s",
            result["intent"],
            result["is_safe"],
            result["analysis_source"],
        )

        return result

    except Exception as exc:
        logger.exception(
            "Combined query analysis failed: %s",
            exc,
        )

        fallback_intent = _fallback_intent(
            normalized_query
        )

        # Deterministic guardrails already passed.
        return _build_result(
            intent=fallback_intent,
            is_safe=True,
            safety_reason="",
            source="fallback",
        )