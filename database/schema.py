import logging
from pathlib import Path
from typing import Dict, List, Union

import pandas as pd

from database.connection import (
    CUSTOMERS_FILE,
    PRODUCTS_FILE,
    DEPARTMENTS_FILE,
    WORKFLOW_TRANSITIONS_FILE,
    ORDERS_FILE,
    CASES_FILE,
    COMPLAINTS_FILE,
    COMPLAINT_ACTIONS_FILE,
    ENQUIRIES_FILE,
    EVIDENCE_REVIEWS_FILE,
    HITL_REVIEWS_FILE,
    DEPARTMENT_TASKS_FILE,
    NOTIFICATIONS_FILE,
    REFUNDS_FILE,
    REPLACEMENTS_FILE,
    VOUCHERS_FILE,
    AUDIT_LOGS_FILE,
)


# =========================================================
# LOGGER
# =========================================================

logger = logging.getLogger(__name__)


# =========================================================
# TYPE ALIAS
# =========================================================

FilePath = Union[str, Path]


# =========================================================
# CSV TABLE SCHEMAS
# =========================================================

TABLE_COLUMNS: Dict[Path, List[str]] = {
    # =====================================================
    # MASTER DATA
    # =====================================================

    Path(CUSTOMERS_FILE): [
        "customer_id",
        "customer_name",
        "email",
        "phone",
        "city",
        "state",
        "pincode",
        "customer_since",
        "loyalty_tier",
    ],

    Path(PRODUCTS_FILE): [
        "product_id",
        "product_name",
        "category",
        "price",
        "warranty_months",
        "return_window_days",
    ],

    Path(DEPARTMENTS_FILE): [
        "department_id",
        "department_name",
        "email",
        "description",
    ],

    Path(WORKFLOW_TRANSITIONS_FILE): [
        "resolution",
        "current_stage",
        "next_stage",
        "department",
        "action",
    ],

    # =====================================================
    # ORDER DATA
    # =====================================================

    Path(ORDERS_FILE): [
        "order_id",
        "customer_id",
        "customer_name",
        "product_id",
        "product_name",
        "category",
        "quantity",
        "order_amount",
        "order_date",
        "delivery_date",
        "order_status",
        "delivery_status",
        "payment_method",
    ],

    # =====================================================
    # CASE DATA
    # =====================================================

    Path(CASES_FILE): [
        "case_id",
        "customer_id",
        "order_id",
        "case_type",
        "current_stage",
        "status",
        "opened_date",
        "closed_date",
    ],

    # =====================================================
    # COMPLAINT DATA
    # =====================================================

    Path(COMPLAINTS_FILE): [
        "complaint_id",
        "case_id",
        "order_id",
        "issue_type",
        "description",
        "complaint_status",
        "priority",
        "assigned_department",
        "evidence_status",
        "resolution_type",
        "resolution_status",
        "resolution_reason",
        "awaiting_resolution_confirmation",
        "customer_resolution_confirmed",
        "department_task_id",
        "created_at",
        "updated_at",
    ],

    Path(COMPLAINT_ACTIONS_FILE): [
        "action_id",
        "case_id",
        "order_id",
        "action_type",
        "action_status",
        "details",
        "created_at",
    ],

    # =====================================================
    # ENQUIRY DATA
    # =====================================================

    Path(ENQUIRIES_FILE): [
        "enquiry_id",
        "case_id",
        "customer_id",
        "query",
        "answer",
        "sources",
        "escalated",
    ],

    # =====================================================
    # IMAGE EVIDENCE DATA
    # =====================================================

    Path(EVIDENCE_REVIEWS_FILE): [
        "evidence_id",
        "case_id",
        "order_id",
        "evidence_type",
        "file_path",
        "description",
        "result",
        "comments",
        "reviewed_by",
        "uploaded_at",
        "reviewed_at",
    ],

    # =====================================================
    # GENERAL HITL REVIEW DATA
    # =====================================================

    Path(HITL_REVIEWS_FILE): [
        "review_id",
        "query",
        "status",
        "human_response",
    ],

    # =====================================================
    # DEPARTMENT TASK DATA
    # =====================================================

    Path(DEPARTMENT_TASKS_FILE): [
        "task_id",
        "case_id",
        "department",
        "action",
        "resolution",
        "status",
        "notes",
        "created_date",
    ],

    # =====================================================
    # NOTIFICATION DATA
    # =====================================================

    Path(NOTIFICATIONS_FILE): [
        "notification_id",
        "case_id",
        "customer_id",
        "message",
        "timestamp",
    ],

    # =====================================================
    # REFUND DATA
    # =====================================================

    Path(REFUNDS_FILE): [
        "refund_id",
        "case_id",
        "order_id",
        "customer_id",
        "amount",
        "status",
        "refund_date",
    ],

    # =====================================================
    # REPLACEMENT DATA
    # =====================================================

    Path(REPLACEMENTS_FILE): [
        "replacement_id",
        "case_id",
        "order_id",
        "customer_id",
        "status",
        "replacement_date",
    ],

    # =====================================================
    # VOUCHER DATA
    # =====================================================

    Path(VOUCHERS_FILE): [
        "voucher_id",
        "case_id",
        "customer_id",
        "amount",
        "status",
        "issued_date",
    ],

    # =====================================================
    # AUDIT LOG DATA
    # =====================================================

    Path(AUDIT_LOGS_FILE): [
        "log_id",
        "case_id",
        "timestamp",
        "action",
        "user",
    ],
}


# =========================================================
# PATH NORMALIZATION
# =========================================================

def normalize_file_path(file_path: FilePath) -> Path:
    """
    Convert a string or Path value into a Path object.
    """

    return Path(file_path)


# =========================================================
# SCHEMA LOOKUP
# =========================================================

def get_table_columns(file_path: FilePath) -> List[str]:
    """
    Return the configuredr a CSV file.

    Raises:
        KeyError: If the CSV file is not registered.
    """

    csv_path = normalize_file_path(file_path)

    if csv_path not in TABLE_COLUMNS:
        raise KeyError(
            f"No schema is registered for CSV file: {csv_path}"
        )

    return TABLE_COLUMNS[csv_path].copy()


# =========================================================
# COLUMN NORMALIZATION
# =========================================================

def normalize_column_name(column_name: object) -> str:
    """
    Normalize a CSV column name for schema comparison.
    """

    return (
        str(column_name)
        .replace("\ufeff", "")
        .strip()
        .lower()
    )


# =========================================================
# SCHEMA VALIDATION
# =========================================================

def validate_table_schema(file_path: FilePath) -> bool:
    """
    Validate the header of an existing CSV file.

    This function does not modify, reset, repair, or overwrite
    the CSV file.
    """

    csv_path = normalize_file_path(file_path)

    if csv_path not in TABLE_COLUMNS:
        logger.error(
            "No schema registered for CSV file: %s",
            csv_path,
        )
        return False

    if not csv_path.exists():
        logger.warning(
            "CSV file does not exist: %s",
            csv_path,
        )
        return False

    if not csv_path.is_file():
        logger.error(
            "Configured CSV path is not a file: %s",
            csv_path,
        )
        return False

    if csv_path.stat().st_size == 0:
        logger.error(
            "CSV file is completely empty: %s",
            csv_path,
        )
        return False

    expected_columns = TABLE_COLUMNS[csv_path]

    try:
        existing_columns = list(
            pd.read_csv(
                csv_path,
                nrows=0,
            ).columns
        )

    except pd.errors.EmptyDataError:
        logger.error(
            "CSV file has no readable header: %s",
            csv_path,
        )
        return False

    except pd.errors.ParserError as exc:
        logger.error(
            "CSV parsing failed. File=%s, Error=%s",
            csv_path,
            exc,
        )
        return False

    except Exception as exc:
        logger.exception(
            "CSV schema validation failed. "
            "File=%s, Error=%s",
            csv_path,
            exc,
        )
        return False

    normalized_existing_columns = [
        normalize_column_name(column)
        for column in existing_columns
    ]

    normalized_expected_columns = [
        normalize_column_name(column)
        for column in expected_columns
    ]

    if normalized_existing_columns != normalized_expected_columns:
        missing_columns = [
            column
            for column in normalized_expected_columns
            if column not in normalized_existing_columns
        ]

        unexpected_columns = [
            column
            for column in normalized_existing_columns
            if column not in normalized_expected_columns
        ]

        logger.warning(
            "CSV schema mismatch. "
            "File=%s, Missing=%s, Unexpected=%s. "
            "The existing CSV was preserved.",
            csv_path,
            missing_columns,
            unexpected_columns,
        )

        return False

    logger.info(
        "CSV schema is valid: %s",
        csv_path,
    )

    return True


# =========================================================
# VALIDATE ALL CSV TABLES
# =========================================================

def validate_all_table_schemas() -> bool:
    """
    Validate all registered CSV files.

    Returns:
        True if all registered CSV files have valid schemas.
        False if one or more files have invalid schemas.
    """

    all_tables_valid = True

    for csv_path in TABLE_COLUMNS:
        if not validate_table_schema(csv_path):
            all_tables_valid = False

    return all_tables_valid


# =========================================================
# CREATE ONLY MISSING CSV FILES
# =========================================================

def ensure_tables_exist() -> None:
    """
    Create CSV files only when they do not already exist.

    Existing CSV files are never overwritten, reset, or emptied.
    """

    logger.info("Checking required CSV files")

    for configured_path, expected_columns in TABLE_COLUMNS.items():
        csv_path = normalize_file_path(configured_path)

        csv_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if csv_path.exists():
            logger.info(
                "CSV already exists and was preserved: %s",
                csv_path,
            )
            continue

        try:
            empty_dataframe = pd.DataFrame(
                columns=expected_columns
            )

            empty_dataframe.to_csv(
                csv_path,
                index=False,
            )

            logger.info(
                "Created missing CSV file: %s",
                csv_path,
            )

        except Exception as exc:
            logger.exception(
                "Failed to create CSV file. "
                "File=%s, Error=%s",
                csv_path,
                exc,
            )
            raise