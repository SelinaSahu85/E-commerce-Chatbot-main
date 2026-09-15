"""
Enquiry Resolution Agent.

Processes general customer enquiries using Policy RAG.

Workflow:
1. Validate the customer question.
2. Create an enquiry case.
3. Check whether the question can be answered safely.
4. Check the JSON response cache.
5. Return the cached answer when available.
6. Call Policy RAG only when the answer is not cached.
7. Save successful general policy answers to the cache.
8. Escalate insufficient or sensitive enquiries to Customer Care.

Dynamic customer-specific questions are not cached.
"""

from typing import Any, Dict, List

from database.repositories import EnquiryRepository
from hitl.customer_care import create_review_request
from services import case_service, notification_service
from tools.enquiry_safety import can_answer_safely
from tools.policy_rag import get_policy_answer
from tools.response_cache import (
    get_cached_response,
    is_cacheable_question,
    save_response_to_cache,
)
from utils.logger import logger


# =========================================================
# BASIC HELPERS
# =========================================================

def _clean_text(value: Any) -> str:
    """
    Convert a value into a clean string.
    """

    if value is None:
        return ""

    return str(value).strip()


def _clean_sources(sources: Any) -> List[str]:
    """
    Convert source data into a clean list of strings.
    """

    if sources is None:
        return []

    if isinstance(sources, str):
        cleaned_source = sources.strip()

        if not cleaned_source:
            return []

        return [cleaned_source]

    if isinstance(sources, (list, tuple, set)):
        cleaned_sources = []

        for source in sources:
            cleaned_source = str(source).strip()

            if cleaned_source:
                cleaned_sources.append(cleaned_source)

        return cleaned_sources

    cleaned_source = str(sources).strip()

    if not cleaned_source:
        return []

    return [cleaned_source]

# =========================================================
# CREATE ENQUIRY CASE
# =========================================================

def _create_enquiry_case(
    customer_id: str,
) -> Dict[str, Any]:
    """
    Create a database case for the customer enquiry.
    """

    case = case_service.create_case(
        customer_id=customer_id,
        order_id="",
        case_type="Enquiry",
    )

    if not case:
        raise RuntimeError(
            "The enquiry case could not be created."
        )

    case_id = _clean_text(
        case.get("case_id")
    )

    if not case_id:
        raise RuntimeError(
            "The enquiry case was created without a Case ID."
        )

    return case


# =========================================================
# HITL ESCALATION
# =========================================================

def _escalate(
    state: Dict[str, Any],
    case_id: str,
    customer_id: str,
    query: str,
    reason: str,
) -> Dict[str, Any]:
    """
    Escalate an enquiry to Customer Care.
    """

    review_id = create_review_request(query)

    EnquiryRepository.create_enquiry(
        case_id=case_id,
        customer_id=customer_id,
        query=query,
        answer="",
        sources=[],
        escalated=True,
    )

    case_service.update_stage(
        case_id=case_id,
        current_stage="Customer Care",
        status="Escalated",
    )

    message = (
        "Your request requires review by Customer Care.\n\n"
        f"**Review ID:** {review_id}\n\n"
        "A support representative will review your request."
    )

    try:
        notification_service.notify_customer(
            case_id=case_id,
            customer_id=customer_id,
            message=message,
        )

    except Exception as exc:
        logger.exception(
            "Customer notification failed. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

    logger.info(
        "HITL triggered. Case ID=%s, Review ID=%s, Reason=%s",
        case_id,
        review_id,
        reason,
    )

    return {
        **state,
        "intent": "enquiry",
        "requires_hitl": True,
        "review_id": review_id,
        "case_id": case_id,
        "sources": [],
        "response": message,
        "cache_hit": False,
    }


# =========================================================
# CACHE RESPONSE HANDLER
# =========================================================

def _handle_cached_response(
    state: Dict[str, Any],
    case_id: str,
    customer_id: str,
    query: str,
    cached_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return a cached response without calling Policy RAG.

    The enquiry is still recorded in enquiries.csv so that
    customer interaction history is preserved.
    """

    cached_answer = _clean_text(
        cached_result.get("answer")
    )

    cached_sources = _clean_sources(
        cached_result.get("sources")
    )

    if not cached_answer:
        raise ValueError(
            "The cached response contains an empty answer."
        )

    EnquiryRepository.create_enquiry(
        case_id=case_id,
        customer_id=customer_id,
        query=query,
        answer=cached_answer,
        sources=cached_sources,
        escalated=False,
    )

    case_service.close_case(
        case_id=case_id,
        reason="Enquiry answered from response cache",
    )

    logger.info(
        "Enquiry answered from cache. "
        "Case ID=%s, Customer ID=%s, Cache Key=%s",
        case_id,
        customer_id,
        cached_result.get("cache_key", ""),
    )

    return {
        **state,
        "intent": "enquiry",
        "requires_hitl": False,
        "review_id": "",
        "case_id": case_id,
        "sources": cached_sources,
        "response": cached_answer,
        "cache_hit": True,
    }


# =========================================================
# GENERATED RESPONSE HANDLER
# =========================================================

def _handle_generated_response(
    state: Dict[str, Any],
    case_id: str,
    customer_id: str,
    query: str,
    result: Dict[str, Any],
    cacheable: bool,
) -> Dict[str, Any]:
    """
    Store and return a successful Policy RAG answer.

    The answer is saved to the JSON cache only when the
    question is suitable for caching.
    """

    generated_answer = _clean_text(
        result.get("answer")
    )

    sources = _clean_sources(
        result.get("sources")
    )

    if not generated_answer:
        raise ValueError(
            "Policy RAG returned an empty answer."
        )

    EnquiryRepository.create_enquiry(
        case_id=case_id,
        customer_id=customer_id,
        query=query,
        answer=generated_answer,
        sources=sources,
        escalated=False,
    )

    case_service.close_case(
        case_id=case_id,
        reason="Enquiry answered",
    )

    if cacheable:
        try:
            cache_saved = save_response_to_cache(
                question=query,
                answer=generated_answer,
                sources=sources,
                intent="enquiry",
                metadata={
                    "answer_type": "policy_rag",
                },
            )

            logger.info(
                "Response cache save completed. "
                "Case ID=%s, Saved=%s",
                case_id,
                cache_saved,
            )

        except Exception as exc:
            # Cache failure should not prevent the customer
            # from receiving the generated answer.
            logger.exception(
                "Failed to save the response to cache. "
                "Case ID=%s, Error=%s",
                case_id,
                exc,
            )

    else:
        logger.info(
            "Response was not cached because the question "
            "contains dynamic or customer-specific information. "
            "Case ID=%s",
            case_id,
        )

    return {
        **state,
        "intent": "enquiry",
        "requires_hitl": False,
        "review_id": "",
        "case_id": case_id,
        "sources": sources,
        "response": generated_answer,
        "cache_hit": False,
    }


# =========================================================
# ENQUIRY AGENT
# =========================================================

def enquiry_agent(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a customer enquiry.
    """

    query = _clean_text(
        state.get("user_query")
    )

    customer_id = _clean_text(
        state.get("customer_id")
    ).upper()

    logger.info(
        "Enquiry Agent started. Customer ID=%s, Query=%s",
        customer_id,
        query,
    )

    state["intent"] = "enquiry"

    # =====================================================
    # 1. VALIDATE QUERY
    # =====================================================

    if not query:
        logger.warning(
            "Enquiry Agent received an empty question."
        )

        return {
            **state,
            "requires_hitl": False,
            "review_id": "",
            "case_id": "",
            "sources": [],
            "response": (
                "Please enter the question you would like "
                "help with."
            ),
            "cache_hit": False,
        }

    # =====================================================
    # 2. CREATE ENQUIRY CASE
    # =====================================================

    try:
        case = _create_enquiry_case(
            customer_id=customer_id
        )

        case_id = _clean_text(
            case.get("case_id")
        )

    except Exception as exc:
        logger.exception(
            "Failed to create an enquiry case. "
            "Customer ID=%s, Error=%s",
            customer_id,
            exc,
        )

        return {
            **state,
            "requires_hitl": False,
            "review_id": "",
            "case_id": "",
            "sources": [],
            "response": (
                "I couldn't create a support case for your "
                "enquiry right now. Please try again."
            ),
            "cache_hit": False,
        }

    # =====================================================
    # 3. SAFETY CHECK
    # =====================================================

    try:
        safe_to_answer = can_answer_safely(query)

    except Exception as exc:
        logger.exception(
            "Enquiry safety check failed. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

        return _escalate(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            reason="safety check failure",
        )

    if not safe_to_answer:
        return _escalate(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            reason="sensitive or unsafe query",
        )

    # =====================================================
    # 4. CHECK WHETHER QUESTION CAN BE CACHED
    # =====================================================

    try:
        cacheable = is_cacheable_question(query)

    except Exception as exc:
        logger.exception(
            "Cacheability check failed. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

        cacheable = False

    logger.info(
        "Enquiry cacheability evaluated. "
        "Case ID=%s, Cacheable=%s",
        case_id,
        cacheable,
    )

    # =====================================================
    # 5. CHECK JSON RESPONSE CACHE
    # =====================================================

    cached_result = None

    if cacheable:
        try:
            cached_result = get_cached_response(
                question=query,
                intent="enquiry",
            )

        except Exception as exc:
            logger.exception(
                "Response cache lookup failed. "
                "Case ID=%s, Error=%s",
                case_id,
                exc,
            )

            cached_result = None

    if cached_result:
        try:
            return _handle_cached_response(
                state=state,
                case_id=case_id,
                customer_id=customer_id,
                query=query,
                cached_result=cached_result,
            )

        except Exception as exc:
            logger.exception(
                "Failed to process cached response. "
                "Case ID=%s, Error=%s",
                case_id,
                exc,
            )

            # Continue to Policy RAG if cached-answer
            # processing fails.

    # =====================================================
    # 6. CALL POLICY RAG
    # =====================================================

    try:
        logger.info(
            "Calling Policy RAG. Case ID=%s",
            case_id,
        )

        result = get_policy_answer(query)

        logger.info(
            "Policy RAG completed. Case ID=%s",
            case_id,
        )

    except Exception as exc:
        logger.exception(
            "Policy RAG failed. Case ID=%s, Error=%s",
            case_id,
            exc,
        )

        return _escalate(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            reason="Policy RAG execution failure",
        )

    # =====================================================
    # 7. VALIDATE POLICY RAG RESULT
    # =====================================================

    if not isinstance(result, dict):
        logger.error(
            "Policy RAG returned an invalid result. "
            "Case ID=%s, Result Type=%s",
            case_id,
            type(result).__name__,
        )

        return _escalate(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            reason="invalid Policy RAG result",
        )

    sufficient = bool(
        result.get("sufficient", False)
    )

    generated_answer = _clean_text(
        result.get("answer")
    )

    if not sufficient or not generated_answer:
        logger.warning(
            "Policy RAG result was insufficient. "
            "Case ID=%s, Sufficient=%s, HasAnswer=%s",
            case_id,
            sufficient,
            bool(generated_answer),
        )

        return _escalate(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            reason="insufficient retrieved information",
        )

    # =====================================================
    # 8. STORE AND RETURN GENERATED RESPONSE
    # =====================================================

    try:
        return _handle_generated_response(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            result=result,
            cacheable=cacheable,
        )

    except Exception as exc:
        logger.exception(
            "Failed to store the generated enquiry response. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

        # Return the generated answer even if writing to the
        # enquiry database or JSON cache fails.
        return {
            **state,
            "intent": "enquiry",
            "requires_hitl": False,
            "review_id": "",
            "case_id": case_id,
            "sources": _clean_sources(
                result.get("sources")
            ),
            "response": generated_answer,
            "cache_hit": False,
        }