import hashlib
import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.logger import logger


# =========================================================
# CACHE CONFIGURATION
# =========================================================

CACHE_FILE = Path(
    "datasets",
    "cache",
    "response_cache.json",
)

CACHE_VERSION = 1

_cache_lock = threading.Lock()


# =========================================================
# CACHE FILE INITIALIZATION
# =========================================================

def ensure_cache_file_exists() -> None:
    """
    Create the response cache file when it does not exist.

    Existing cache data is never overwritten.
    """

    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if CACHE_FILE.exists():
        return

    initial_data = {
        "version": CACHE_VERSION,
        "entries": {},
    }

    _write_cache_data(initial_data)

    logger.info(
        "Response cache created. File=%s",
        CACHE_FILE,
    )


# =========================================================
# QUESTION NORMALIZATION
# =========================================================

def normalize_question(question: Any) -> str:
    """
    Normalize a customer question before cache lookup.

    Examples:
        " What is the RETURN policy? "
            becomes
        "what is the return policy"

        "How   can I return an item"
            becomes
        "how can i return an item"
    """

    normalized = str(
        question or ""
    ).strip().lower()

    if not normalized:
        return ""

    normalized = re.sub(
        r"[^\w\s]",
        " ",
        normalized,
        flags=re.UNICODE,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    return normalized


def generate_cache_key(
    question: Any,
    intent: str = "enquiry",
) -> str:
    """
    Generate a deterministic cache key.

    Intent is included so the same text under different
    workflows does not reuse an unrelated answer.
    """

    normalized_question = normalize_question(
        question
    )

    normalized_intent = str(
        intent or "enquiry"
    ).strip().lower()

    value_to_hash = (
        f"{normalized_intent}:{normalized_question}"
    )

    return hashlib.sha256(
        value_to_hash.encode("utf-8")
    ).hexdigest()


# =========================================================
# CACHE READ AND WRITE
# =========================================================

def _read_cache_data() -> Dict[str, Any]:
    """
    Read the complete JSON cache safely.
    """

    ensure_cache_file_exists()

    try:
        with CACHE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as exc:
        logger.exception(
            "Response cache contains invalid JSON. "
            "File=%s, Error=%s",
            CACHE_FILE,
            exc,
        )

        return {
            "version": CACHE_VERSION,
            "entries": {},
        }

    except Exception as exc:
        logger.exception(
            "Failed to read response cache. "
            "File=%s, Error=%s",
            CACHE_FILE,
            exc,
        )

        return {
            "version": CACHE_VERSION,
            "entries": {},
        }

    if not isinstance(data, dict):
        return {
            "version": CACHE_VERSION,
            "entries": {},
        }

    if not isinstance(
        data.get("entries"),
        dict,
    ):
        data["entries"] = {}

    data.setdefault(
        "version",
        CACHE_VERSION,
    )

    return data


def _write_cache_data(
    data: Dict[str, Any],
) -> None:
    """
    Write cache data atomically.

    A temporary file is written first and then replaces the
    original file. This reduces the risk of an empty or
    partially written JSON file.
    """

    CACHE_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = CACHE_FILE.with_suffix(
        ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temporary_file.replace(
        CACHE_FILE
    )


# =========================================================
# CACHE LOOKUP
# =========================================================

def get_cached_response(
    question: Any,
    intent: str = "enquiry",
) -> Optional[Dict[str, Any]]:
    """
    Return a cached response when an exact normalized question
    match exists.

    Returns None when no cache entry exists.
    """

    normalized_question = normalize_question(
        question
    )

    if not normalized_question:
        return None

    cache_key = generate_cache_key(
        question=normalized_question,
        intent=intent,
    )

    with _cache_lock:
        cache_data = _read_cache_data()

        entry = cache_data.get(
            "entries",
            {},
        ).get(cache_key)

    if not entry:
        logger.info(
            "Response cache miss. "
            "Intent=%s, Question=%s",
            intent,
            normalized_question,
        )

        return None

    cached_answer = str(
        entry.get("answer", "")
    ).strip()

    if not cached_answer:
        logger.warning(
            "Cache entry contains an empty answer. "
            "Cache Key=%s",
            cache_key,
        )

        return None

    logger.info(
        "Response cache hit. "
        "Intent=%s, Cache Key=%s",
        intent,
        cache_key,
    )

    return {
        "answer": cached_answer,
        "sources": entry.get(
            "sources",
            [],
        ),
        "cache_key": cache_key,
        "cached": True,
        "created_at": entry.get(
            "created_at",
            "",
        ),
    }


# =========================================================
# SAVE RESPONSE
# =========================================================

def save_response_to_cache(
    question: Any,
    answer: Any,
    sources: Optional[List[str]] = None,
    intent: str = "enquiry",
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Save an LLM-generated answer in the JSON cache.

    Existing entries for the same normalized question are
    updated rather than duplicated.
    """

    normalized_question = normalize_question(
        question
    )

    normalized_answer = str(
        answer or ""
    ).strip()

    normalized_intent = str(
        intent or "enquiry"
    ).strip().lower()

    if not normalized_question:
        logger.warning(
            "Empty question was not saved to cache."
        )

        return False

    if not normalized_answer:
        logger.warning(
            "Empty response was not saved to cache. "
            "Question=%s",
            normalized_question,
        )

        return False

    normalized_sources = [
        str(source).strip()
        for source in (sources or [])
        if str(source).strip()
    ]

    cache_key = generate_cache_key(
        question=normalized_question,
        intent=normalized_intent,
    )

    timestamp = datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    with _cache_lock:
        cache_data = _read_cache_data()

        entries = cache_data.setdefault(
            "entries",
            {},
        )

        existing_entry = entries.get(
            cache_key,
            {},
        )

        created_at = existing_entry.get(
            "created_at",
            timestamp,
        )

        entries[cache_key] = {
            "question": str(
                question or ""
            ).strip(),
            "normalized_question": normalized_question,
            "answer": normalized_answer,
            "intent": normalized_intent,
            "sources": normalized_sources,
            "metadata": metadata or {},
            "created_at": created_at,
            "updated_at": timestamp,
        }

        _write_cache_data(
            cache_data
        )

    logger.info(
        "Response saved to cache. "
        "Intent=%s, Cache Key=%s",
        normalized_intent,
        cache_key,
    )

    return True


# =========================================================
# DELETE ONE CACHE ENTRY
# =========================================================

def delete_cached_response(
    question: Any,
    intent: str = "enquiry",
) -> bool:
    """
    Delete one cached question and answer.
    """

    normalized_question = normalize_question(
        question
    )

    if not normalized_question:
        return False

    cache_key = generate_cache_key(
        question=normalized_question,
        intent=intent,
    )

    with _cache_lock:
        cache_data = _read_cache_data()
        entries = cache_data.get(
            "entries",
            {},
        )

        if cache_key not in entries:
            return False

        del entries[cache_key]

        _write_cache_data(
            cache_data
        )

    logger.info(
        "Cached response deleted. Cache Key=%s",
        cache_key,
    )

    return True


# =========================================================
# CLEAR COMPLETE CACHE
# =========================================================

def clear_response_cache() -> int:
    """
    Remove every cached response.

    Returns the number of entries removed.
    """

    with _cache_lock:
        cache_data = _read_cache_data()

        removed_count = len(
            cache_data.get(
                "entries",
                {},
            )
        )

        empty_cache = {
            "version": CACHE_VERSION,
            "entries": {},
        }

        _write_cache_data(
            empty_cache
        )

    logger.info(
        "Response cache cleared. Entries removed=%s",
        removed_count,
    )

    return removed_count


# =========================================================
# CACHE STATISTICS
# =========================================================

def get_cache_statistics() -> Dict[str, Any]:
    """
    Return basic response-cache information.
    """

    with _cache_lock:
        cache_data = _read_cache_data()

    entries = cache_data.get(
        "entries",
        {},
    )

    return {
        "cache_file": str(CACHE_FILE),
        "entry_count": len(entries),
        "version": cache_data.get(
            "version",
            CACHE_VERSION,
        ),
    }

def is_cacheable_question(question: Any) -> bool:
    """
    Determine whether a customer question can be cached.

    General policy and FAQ questions can be cached.

    Customer-specific and live-status questions must not be
    cached because the answer can change over time.
    """

    normalized_question = normalize_question(
        question
    )

    if not normalized_question:
        return False

    dynamic_phrases = {
        "my order",
        "order status",
        "my complaint",
        "complaint status",
        "my case",
        "case status",
        "my refund",
        "refund status",
        "my replacement",
        "replacement status",
        "my evidence",
        "evidence status",
        "my delivery",
        "delivery status",
        "where is my order",
        "track my order",
        "customer information",
    }

    for phrase in dynamic_phrases:
        if phrase in normalized_question:
            logger.info(
                "Question is not cacheable because it contains "
                "dynamic phrase=%s",
                phrase,
            )
            return False

    dynamic_id_patterns = [
        r"\bord\s*\d+\b",
        r"\bcase\s*\d+\b",
        r"\bcmp\s*\d+\b",
        r"\btask\s*\d+\b",
        r"\bref\s*\d+\b",
        r"\brep\s*\d+\b",
    ]

    for pattern in dynamic_id_patterns:
        if re.search(
            pattern,
            normalized_question,
            flags=re.IGNORECASE,
        ):
            logger.info(
                "Question is not cacheable because it contains "
                "a transaction identifier."
            )
            return False

    return True