"""
Enquiry Resolution Agent.

Processes safe customer enquiries using Policy RAG.

Workflow:
1. Validate the customer question.
2. Read the safety result produced by the Supervisor Agent.
3. Create an enquiry case.
4. Check whether the question is cacheable.
5. Return the cached answer when available.
6. Call Policy RAG only when the answer is not cached.
7. Save successful general-policy answers to the cache.
8. Escalate insufficient Policy RAG results to Customer Care.

Intent and safety classification are already completed by
tools/query_analyzer.py through the Supervisor Agent.
"""

from typing import Any, Dict

from database.repositories import EnquiryRepository
from hitl.customer_care import create_review_request
from services import case_service, notification_service
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


def _as_boolean(
    value: Any,
    default: bool = False,
) -> bool:
    """
    Convert common Boolean representations into a Boolean.
    """

    if isinstance(value, bool):
        return value

    if value is None:
        return default

    normalized_value = str(
        value
    ).strip().lower()

    if normalized_value in {
        "true",
        "1",
        "yes",
        "safe",
    }:
        return True

    if normalized_value in {
        "false",
        "0",
        "no",
        "hitl",
        "unsafe",
    }:
        return False

    return default


# =========================================================
# CREATE ENQUIRY CASE
# =========================================================

def _create_enquiry_case(
    customer_id: str,
) -> Dict[str, Any]:
    """
    Create a database case for the customer enquiry.
    """

    if not customer_id:
        raise ValueError(
            "Customer ID is required to create an enquiry case."
        )

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

    normalized_reason = (
        _clean_text(reason)
        or "The enquiry requires human review."
    )

    review_id = _clean_text(
        state.get("review_id")
    )

    if not review_id:
        try:
            review_id = _clean_text(
                create_review_request(
                    query
                )
            )

        except Exception as exc:
            logger.exception(
                "Failed to create HITL review request. "
                "Case ID=%s, Error=%s",
                case_id,
                exc,
            )

            review_id = ""

    try:
        EnquiryRepository.create_enquiry(
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            answer="",
            sources=[],
            escalated=True,
        )

    except Exception as exc:
        logger.exception(
            "Failed to store escalated enquiry. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

    try:
        case_service.update_stage(
            case_id=case_id,
            current_stage="Customer Care",
            status="Escalated",
        )

    except Exception as exc:
        logger.exception(
            "Failed to update enquiry case stage. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

    message = (
        "Your request requires review by our "
        "Customer Care team.\n\n"
    )

    if review_id:
        message += (
            f"**Review ID:** {review_id}\n\n"
        )

    message += (
        "A support representative will review your request "
        "and provide further assistance."
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
        "Enquiry escalated to HITL. "
        "Case ID=%s, Review ID=%s, Reason=%s",
        case_id,
        review_id,
        normalized_reason,
    )

    return {
        **state,
        "intent": "enquiry",
        "is_safe": False,
        "safety_reason": normalized_reason,
        "requires_hitl": True,
        "review_id": review_id,
        "case_id": case_id,
        "sources": [],
        "response": message,
        "cache_hit": False,
    }


# =========================================================
# DEFENSIVE SENSITIVE QUERY HANDLER
# =========================================================

def _handle_sensitive_query(
    state: Dict[str, Any],
    query: str,
) -> Dict[str, Any]:
    """
    Handle a sensitive enquiry that reaches this agent.

    Normally, the Supervisor Agent routes sensitive enquiries
    directly to HITL. This is a defensive fallback and does not
    perform another LLM safety check.
    """

    review_id = _clean_text(
        state.get("review_id")
    )

    safety_reason = _clean_text(
        state.get("safety_reason")
    )

    if not safety_reason:
        safety_reason = (
            "The request contains sensitive information "
            "or requires human assistance."
        )

    response = _clean_text(
        state.get("response")
    )

    if not response:
        response = (
            "This request contains sensitive information or "
            "requires an action that cannot be completed "
            "automatically.\n\n"
            "The request has been forwarded to our "
            "Customer Care team for human review."
        )

        if review_id:
            response += (
                f"\n\n**Review ID:** {review_id}"
            )

    logger.warning(
        "Sensitive enquiry reached Enquiry Agent. "
        "Query=%s, Review ID=%s, Reason=%s",
        query,
        review_id,
        safety_reason,
    )

    return {
        **state,
        "intent": "enquiry",
        "is_safe": False,
        "safety_reason": safety_reason,
        "requires_hitl": True,
        "review_id": review_id,
        "sources": [],
        "response": response,
        "cache_hit": False,
    }


# =========================================================
# CACHED RESPONSE HANDLER
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
    """

    cached_answer = _clean_text(
        cached_result.get("answer")
    )

    raw_sources = cached_result.get(
        "sources",
        [],
    )

    if raw_sources is None:
        cached_sources = []

    elif isinstance(raw_sources, str):
        source_value = raw_sources.strip()

        if source_value:
            cached_sources = [
                source_value
            ]
        else:
            cached_sources = []

    elif isinstance(
        raw_sources,
        (
            list,
            tuple,
            set,
        ),
    ):
        cached_sources = [
            str(source).strip()
            for source in raw_sources
            if str(source).strip()
        ]

    else:
        source_value = str(
            raw_sources
        ).strip()

        if source_value:
            cached_sources = [
                source_value
            ]
        else:
            cached_sources = []

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
        cached_result.get(
            "cache_key",
            "",
        ),
    )

    return {
        **state,
        "intent": "enquiry",
        "is_safe": True,
        "safety_reason": "",
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
    """

    generated_answer = _clean_text(
        result.get("answer")
    )

    raw_sources = result.get(
        "sources",
        [],
    )

    if raw_sources is None:
        sources = []

    elif isinstance(raw_sources, str):
        source_value = raw_sources.strip()

        if source_value:
            sources = [
                source_value
            ]
        else:
            sources = []

    elif isinstance(
        raw_sources,
        (
            list,
            tuple,
            set,
        ),
    ):
        sources = [
            str(source).strip()
            for source in raw_sources
            if str(source).strip()
        ]

    else:
        source_value = str(
            raw_sources
        ).strip()

        if source_value:
            sources = [
                source_value
            ]
        else:
            sources = []

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
            logger.exception(
                "Failed to save response to cache. "
                "Case ID=%s, Error=%s",
                case_id,
                exc,
            )

    else:
        logger.info(
            "Response was not cached because the question "
            "is dynamic or customer-specific. Case ID=%s",
            case_id,
        )

    return {
        **state,
        "intent": "enquiry",
        "is_safe": True,
        "safety_reason": "",
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

    The Supervisor Agent provides:
    - is_safe
    - safety_reason
    - analysis_source
    - review_id
    """

    query = _clean_text(
        state.get("user_query")
    )

    customer_id = _clean_text(
        state.get("customer_id")
    ).upper()

    is_safe = _as_boolean(
        state.get("is_safe"),
        default=True,
    )

    analysis_source = _clean_text(
        state.get("analysis_source")
    )

    logger.info(
        "Enquiry Agent started. "
        "Customer ID=%s, Query=%s, Safe=%s, Source=%s",
        customer_id,
        query,
        is_safe,
        analysis_source,
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
    # 2. READ SUPERVISOR SAFETY RESULT
    # =====================================================

    if not is_safe:
        return _handle_sensitive_query(
            state=state,
            query=query,
        )

    # =====================================================
    # 3. VALIDATE CUSTOMER
    # =====================================================

    if not customer_id:
        logger.warning(
            "Enquiry Agent received an empty Customer ID."
        )

        return {
            **state,
            "requires_hitl": False,
            "review_id": "",
            "case_id": "",
            "sources": [],
            "response": (
                "I couldn't identify the customer account. "
                "Please select a customer and try again."
            ),
            "cache_hit": False,
        }

    # =====================================================
    # 4. CREATE ENQUIRY CASE
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
    # 5. CHECK CACHEABILITY
    # =====================================================

    try:
        cacheable = is_cacheable_question(
            query
        )

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
    # 6. CHECK RESPONSE CACHE
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

    # =====================================================
    # 7. CALL POLICY RAG
    # =====================================================

    try:
        logger.info(
            "Calling Policy RAG. Case ID=%s",
            case_id,
        )

        result = get_policy_answer(
            query
        )

        logger.info(
            "Policy RAG completed. Case ID=%s",
            case_id,
        )

    except Exception as exc:
        logger.exception(
            "Policy RAG failed. "
            "Case ID=%s, Error=%s",
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
    # 8. VALIDATE POLICY RAG RESULT
    # =====================================================

    if not isinstance(
        result,
        dict,
    ):
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
            reason="Invalid Policy RAG result",
        )

    sufficient = _as_boolean(
        result.get("sufficient"),
        default=False,
    )

    generated_answer = _clean_text(
        result.get("answer")
    )

    if (
        not sufficient
        or not generated_answer
    ):
        logger.warning(
            "Policy RAG result was insufficient. "
            "Case ID=%s, Sufficient=%s, Has Answer=%s",
            case_id,
            sufficient,
            bool(generated_answer),
        )

        return _escalate(
            state=state,
            case_id=case_id,
            customer_id=customer_id,
            query=query,
            reason=(
                "Insufficient retrieved policy information"
            ),
        )

    # =====================================================
    # 9. STORE AND RETURN GENERATED RESPONSE
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
            "Failed to store generated enquiry response. "
            "Case ID=%s, Error=%s",
            case_id,
            exc,
        )

        raw_sources = result.get(
            "sources",
            [],
        )

        if raw_sources is None:
            fallback_sources = []

        elif isinstance(raw_sources, str):
            source_value = raw_sources.strip()

            fallback_sources = (
                [source_value]
                if source_value
                else []
            )

        elif isinstance(
            raw_sources,
            (
                list,
                tuple,
                set,
            ),
        ):
            fallback_sources = [
                str(source).strip()
                for source in raw_sources
                if str(source).strip()
            ]

        else:
            source_value = str(
                raw_sources
            ).strip()

            fallback_sources = (
                [source_value]
                if source_value
                else []
            )

        return {
            **state,
            "intent": "enquiry",
            "is_safe": True,
            "safety_reason": "",
            "requires_hitl": False,
            "review_id": "",
            "case_id": case_id,
            "sources": fallback_sources,
            "response": generated_answer,
            "cache_hit": False,
        }