import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from database.connection import (
    read_csv,
    append_row,
    update_rows,
    CUSTOMERS_FILE,
    ORDERS_FILE,
    PRODUCTS_FILE,
    DEPARTMENTS_FILE,
    WORKFLOW_TRANSITIONS_FILE,
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
from database.schema import TABLE_COLUMNS
from utils.logger import logger


# =========================================================
# DATE HELPERS
# =========================================================

def _now():
    """
    Return the current date and time.
    """

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _today():
    """
    Return the current date.
    """

    return datetime.now().strftime(
        "%Y-%m-%d"
    )


def _normalize_id(value):
    """
    Normalize identifiers such as Case ID, Order ID,
    Customer ID, and Evidence ID.
    """

    return str(value or "").strip().upper()


def _normalize_text(value):
    """
    Convert a value to a clean string.
    """

    return str(value or "").strip()


def _normalize_status(value):
    """
    Convert a status value to uppercase.
    """

    return str(value or "").strip().upper()


def _is_true(value):
    """
    Convert common stored Boolean values to a Boolean.
    """

    return str(value or "").strip().upper() in {
        "TRUE",
        "YES",
        "Y",
        "1",
    }


# =========================================================
# BASE REPOSITORY
# =========================================================

class BaseRepository:
    """
    Base repository for CSV-backed data storage.
    """

    FILE = None

    @classmethod
    def _columns(cls):
        """
        Return the configured columns for this repository.
        """

        if cls.FILE is None:
            raise ValueError(
                f"{cls.__name__}.FILE is not configured."
            )

        file_path = Path(cls.FILE)

        if file_path not in TABLE_COLUMNS:
            raise KeyError(
                f"No schema is registered for {file_path}"
            )

        return TABLE_COLUMNS[file_path].copy()

    @classmethod
    def all(cls):
        """
        Return every record from the repository.
        """

        return read_csv(cls.FILE)

    @classmethod
    def create(cls, row):
        """
        Create a new CSV record.
        """

        if not isinstance(row, dict):
            raise TypeError(
                "Repository create expects a dictionary."
            )

        columns = cls._columns()

        valid_row = {
            column: row.get(column, "")
            for column in columns
        }

        append_row(
            cls.FILE,
            columns,
            valid_row,
        )

        return valid_row

    @classmethod
    def update(cls, match, updates):
        """
        Update records matching the supplied conditions.
        """

        if not isinstance(match, dict):
            raise TypeError(
                "Repository match must be a dictionary."
            )

        if not isinstance(updates, dict):
            raise TypeError(
                "Repository updates must be a dictionary."
            )

        valid_columns = cls._columns()

        invalid_match_columns = [
            column
            for column in match
            if column not in valid_columns
        ]

        if invalid_match_columns:
            raise ValueError(
                f"Invalid match columns for {cls.__name__}: "
                f"{invalid_match_columns}"
            )

        invalid_update_columns = [
            column
            for column in updates
            if column not in valid_columns
        ]

        if invalid_update_columns:
            raise ValueError(
                f"Invalid update columns for {cls.__name__}: "
                f"{invalid_update_columns}"
            )

        return update_rows(
            cls.FILE,
            valid_columns,
            match,
            updates,
        )

    @classmethod
    def find_by(cls, **match):
        """
        Return every row matching the supplied values.
        """

        dataframe = cls.all()

        if dataframe.empty:
            return dataframe

        invalid_columns = [
            column
            for column in match
            if column not in dataframe.columns
        ]

        if invalid_columns:
            raise ValueError(
                f"Invalid columns for {cls.__name__}: "
                f"{invalid_columns}"
            )

        mask = pd.Series(
            True,
            index=dataframe.index,
            dtype=bool,
        )

        for column, value in match.items():
            mask &= (
                dataframe[column]
                .astype(str)
                .str.strip()
                .str.upper()
                == str(value or "").strip().upper()
            )

        return dataframe[mask].copy()

    @classmethod
    def get(cls, **match):
        """
        Return the first matching record.
        """

        rows = cls.find_by(**match)

        if rows.empty:
            return None

        return rows.iloc[0].to_dict()


# =========================================================
# CUSTOMER REPOSITORY
# =========================================================

class CustomerRepository(BaseRepository):
    FILE = CUSTOMERS_FILE

    @classmethod
    def get_by_id(cls, customer_id):
        return cls.get(
            customer_id=_normalize_id(customer_id)
        )


# =========================================================
# ORDER REPOSITORY
# =========================================================

class OrderRepository(BaseRepository):
    FILE = ORDERS_FILE

    @classmethod
    def get_by_id(cls, order_id):
        return cls.get(
            order_id=_normalize_id(order_id)
        )

    @classmethod
    def get_by_customer(cls, customer_id):
        return cls.find_by(
            customer_id=_normalize_id(customer_id)
        )


# =========================================================
# PRODUCT REPOSITORY
# =========================================================

class ProductRepository(BaseRepository):
    FILE = PRODUCTS_FILE

    @classmethod
    def get_by_id(cls, product_id):
        return cls.get(
            product_id=_normalize_id(product_id)
        )


# =========================================================
# DEPARTMENT REPOSITORY
# =========================================================

class DepartmentRepository(BaseRepository):
    FILE = DEPARTMENTS_FILE

    @classmethod
    def get_by_id(cls, department_id):
        return cls.get(
            department_id=_normalize_id(department_id)
        )


# =========================================================
# WORKFLOW TRANSITION REPOSITORY
# =========================================================

class WorkflowTransitionRepository(BaseRepository):
    FILE = WORKFLOW_TRANSITIONS_FILE

    @classmethod
    def next_step(
        cls,
        resolution,
        current_stage,
    ):
        """
        Return the configured next workflow transition.
        """

        rows = cls.find_by(
            resolution=resolution,
            current_stage=current_stage,
        )

        if rows.empty:
            return None

        return rows.iloc[0].to_dict()


# =========================================================
# CASE REPOSITORY
# =========================================================

class CaseRepository(BaseRepository):
    FILE = CASES_FILE

    @classmethod
    def get_by_id(cls, case_id):
        return cls.get(
            case_id=_normalize_id(case_id)
        )

    @classmethod
    def create_case(
        cls,
        customer_id,
        order_id,
        case_type,
        current_stage="Open",
        status="Open",
        case_id=None,
    ):
        """
        Create a new enquiry or complaint case.
        """

        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            normalized_case_id = (
                f"CASE{uuid.uuid4().hex[:8].upper()}"
            )

        row = {
            "case_id": normalized_case_id,
            "customer_id": _normalize_id(customer_id),
            "order_id": _normalize_id(order_id),
            "case_type": _normalize_text(case_type),
            "current_stage": _normalize_text(
                current_stage or "Open"
            ),
            "status": _normalize_text(
                status or "Open"
            ),
            "opened_date": _today(),
            "closed_date": "",
        }

        cls.create(row)

        logger.info(
            "Case created. Case ID=%s, Customer ID=%s, "
            "Order ID=%s, Type=%s",
            normalized_case_id,
            row["customer_id"],
            row["order_id"],
            row["case_type"],
        )

        return row

    @classmethod
    def update_stage(
        cls,
        case_id,
        current_stage=None,
        status=None,
    ):
        """
        Update a case workflow stage or status.
        """

        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        updates = {}

        if current_stage is not None:
            updates["current_stage"] = _normalize_text(
                current_stage
            )

        if status is not None:
            updates["status"] = _normalize_text(status)

            if _normalize_status(status) == "CLOSED":
                updates["closed_date"] = _today()

        if not updates:
            return 0

        return cls.update(
            {"case_id": normalized_case_id},
            updates,
        )

    @classmethod
    def open_cases_for_order(
        cls,
        order_id,
        exclude_case_id=None,
    ):
        """
        Return open cases for an Order ID.
        """

        rows = cls.find_by(
            order_id=_normalize_id(order_id)
        )

        if rows.empty:
            return rows

        if "status" in rows.columns:
            rows = rows[
                rows["status"]
                .astype(str)
                .str.strip()
                .str.upper()
                != "CLOSED"
            ].copy()

        if exclude_case_id:
            normalized_case_id = _normalize_id(
                exclude_case_id
            )

            rows = rows[
                rows["case_id"]
                .astype(str)
                .str.strip()
                .str.upper()
                != normalized_case_id
            ].copy()

        return rows


# =========================================================
# COMPLAINT REPOSITORY
# =========================================================

class ComplaintRepository(BaseRepository):
    """
    Repository for creating and updating complaints.
    """

    FILE = COMPLAINTS_FILE

    @classmethod
    def create_complaint(
        cls,
        customer_id,
        order_id,
        product_id,
        description,
        issue_type,
    ):
        """
        Register a complaint for an existing order.

        If an active complaint already exists, return the
        existing complaint instead of creating a duplicate.
        """

        normalized_customer_id = _normalize_id(customer_id)
        normalized_order_id = _normalize_id(order_id)
        normalized_product_id = _normalize_id(product_id)
        normalized_description = _normalize_text(description)
        normalized_issue_type = _normalize_status(
            issue_type or "OTHER"
        )

        if not normalized_customer_id:
            raise ValueError(
                "Customer ID is required."
            )

        if not normalized_order_id:
            raise ValueError(
                "Order ID is required."
            )

        if not normalized_description:
            raise ValueError(
                "Complaint description is required."
            )

        existing_complaint = cls.get_by_order(
            normalized_order_id
        )

        if existing_complaint:
            existing_status = _normalize_status(
                existing_complaint.get(
                    "complaint_status"
                )
            )

            if existing_status not in {
                "RESOLVED",
                "CLOSED",
                "CANCELLED",
            }:
                logger.warning(
                    "Active complaint already exists for "
                    "Order ID=%s.",
                    normalized_order_id,
                )

                return existing_complaint

        complaint_id = (
            f"CMP{uuid.uuid4().hex[:8].upper()}"
        )

        case_id = (
            f"CASE{uuid.uuid4().hex[:8].upper()}"
        )

        evidence_required = (
            normalized_issue_type
            in {
                "DAMAGED_PRODUCT",
                "DEFECTIVE_PRODUCT",
                "WRONG_ITEM",
                "MISSING_ITEM",
            }
        )

        priority = (
            "HIGH"
            if normalized_issue_type
            in {
                "DAMAGED_PRODUCT",
                "DEFECTIVE_PRODUCT",
            }
            else "MEDIUM"
        )

        evidence_status = (
            "NOT_SUBMITTED"
            if evidence_required
            else "NOT_REQUIRED"
        )

        complaint_status = (
            "AWAITING_EVIDENCE"
            if evidence_required
            else "OPEN"
        )

        timestamp = _now()

        case_row = CaseRepository.create_case(
            customer_id=normalized_customer_id,
            order_id=normalized_order_id,
            case_type="COMPLAINT",
            current_stage=complaint_status,
            status="OPEN",
            case_id=case_id,
        )

        case_id = case_row["case_id"]

        row = {
            "complaint_id": complaint_id,
            "case_id": case_id,
            "order_id": normalized_order_id,
            "issue_type": normalized_issue_type,
            "description": normalized_description,
            "complaint_status": complaint_status,
            "priority": priority,

            # Department is assigned only after confirmation.
            "assigned_department": "",

            "evidence_status": evidence_status,
            "resolution_type": "",
            "resolution_status": "NOT_STARTED",
            "resolution_reason": "",
            "awaiting_resolution_confirmation": "False",
            "customer_resolution_confirmed": "False",
            "department_task_id": "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        cls.create(row)

        logger.info(
            "Complaint registered. Complaint ID=%s, "
            "Case ID=%s, Customer ID=%s, Order ID=%s, "
            "Product ID=%s, Issue Type=%s",
            complaint_id,
            case_id,
            normalized_customer_id,
            normalized_order_id,
            normalized_product_id,
            normalized_issue_type,
        )

        return row

    @classmethod
    def get_by_case(cls, case_id):
        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            return None

        return cls.get(
            case_id=normalized_case_id
        )

    @classmethod
    def get_by_order(cls, order_id):
        """
        Return the latest complaint for an Order ID.
        """

        normalized_order_id = _normalize_id(order_id)

        if not normalized_order_id:
            return None

        rows = cls.find_by(
            order_id=normalized_order_id
        )

        if rows.empty:
            return None

        if "updated_at" in rows.columns:
            rows = rows.copy()

            rows["_updated_at"] = pd.to_datetime(
                rows["updated_at"],
                errors="coerce",
            )

            rows = rows.sort_values(
                by="_updated_at",
                ascending=False,
                na_position="last",
            )

        complaint = rows.iloc[0].to_dict()
        complaint.pop("_updated_at", None)

        return complaint

    @staticmethod
    def _is_waiting_for_confirmation(complaint):
        """
        Check whether a complaint is waiting for customer
        resolution confirmation.
        """

        if not complaint:
            return False

        return (
            _is_true(
                complaint.get(
                    "awaiting_resolution_confirmation"
                )
            )
            and _normalize_status(
                complaint.get("resolution_status")
            )
            == "RECOMMENDED"
        )

    @classmethod
    def get_pending_resolution_confirmation(
        cls,
        customer_id=None,
        order_id=None,
        case_id=None,
    ):
        """
        Return the latest complaint waiting for customer
        confirmation.
        """

        if case_id:
            complaint = cls.get_by_case(case_id)

            if cls._is_waiting_for_confirmation(
                complaint
            ):
                return complaint

            return None

        if order_id:
            complaint = cls.get_by_order(order_id)

            if cls._is_waiting_for_confirmation(
                complaint
            ):
                return complaint

            return None

        normalized_customer_id = _normalize_id(
            customer_id
        )

        if not normalized_customer_id:
            return None

        customer_cases = CaseRepository.find_by(
            customer_id=normalized_customer_id
        )

        if customer_cases.empty:
            return None

        complaints = cls.all()

        if complaints.empty:
            return None

        case_ids = {
            _normalize_id(value)
            for value in customer_cases["case_id"].tolist()
            if _normalize_id(value)
        }

        matching_rows = complaints[
            complaints["case_id"]
            .astype(str)
            .str.strip()
            .str.upper()
            .isin(case_ids)
        ].copy()

        if matching_rows.empty:
            return None

        matching_rows["_updated_at"] = pd.to_datetime(
            matching_rows["updated_at"],
            errors="coerce",
        )

        matching_rows = matching_rows.sort_values(
            by="_updated_at",
            ascending=False,
            na_position="last",
        )

        for _, row in matching_rows.iterrows():
            complaint = row.to_dict()
            complaint.pop("_updated_at", None)

            if cls._is_waiting_for_confirmation(
                complaint
            ):
                return complaint

        return None

    @classmethod
    def set_recommended_resolution(
        cls,
        case_id,
        resolution_type,
        resolution_status="RECOMMENDED",
        resolution_reason="",
    ):
        """
        Save the resolution-agent recommendation.

        No department task is created at this stage.
        """

        normalized_case_id = _normalize_id(case_id)
        normalized_resolution = _normalize_status(
            resolution_type
        )
        normalized_status = _normalize_status(
            resolution_status or "RECOMMENDED"
        )

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        if normalized_resolution not in {
            "RETURN",
            "REFUND",
            "REPLACEMENT",
        }:
            raise ValueError(
                "Resolution type must be RETURN, REFUND, "
                "or REPLACEMENT."
            )

        if normalized_status != "RECOMMENDED":
            raise ValueError(
                "Resolution status must be RECOMMENDED."
            )

        complaint = cls.get_by_case(
            normalized_case_id
        )

        if not complaint:
            raise ValueError(
                f"Complaint not found for Case ID: "
                f"{normalized_case_id}"
            )

        updated_count = cls.update(
            {"case_id": normalized_case_id},
            {
                "resolution_type": normalized_resolution,
                "resolution_status": "RECOMMENDED",
                "resolution_reason": _normalize_text(
                    resolution_reason
                ),
                "awaiting_resolution_confirmation": "True",
                "customer_resolution_confirmed": "False",
                "assigned_department": "",
                "department_task_id": "",
                "complaint_status": (
                    "AWAITING_CUSTOMER_CONFIRMATION"
                ),
                "updated_at": _now(),
            },
        )

        if updated_count:
            CaseRepository.update_stage(
                case_id=normalized_case_id,
                current_stage=(
                    "AWAITING_CUSTOMER_CONFIRMATION"
                ),
                status="OPEN",
            )

        logger.info(
            "Resolution recommendation saved. "
            "Case ID=%s, Resolution=%s, Updated=%s",
            normalized_case_id,
            normalized_resolution,
            updated_count,
        )

        return updated_count

    @classmethod
    def mark_manual_review_required(
        cls,
        case_id,
        resolution_reason="",
    ):
        """
        Send the complaint to Case Manager review.
        """

        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        updated_count = cls.update(
            {"case_id": normalized_case_id},
            {
                "resolution_type": "",
                "resolution_status": (
                    "MANUAL_REVIEW_REQUIRED"
                ),
                "resolution_reason": _normalize_text(
                    resolution_reason
                ),
                "awaiting_resolution_confirmation": "False",
                "customer_resolution_confirmed": "False",
                "complaint_status": (
                    "MANUAL_REVIEW_REQUIRED"
                ),
                "updated_at": _now(),
            },
        )

        if updated_count:
            CaseRepository.update_stage(
                case_id=normalized_case_id,
                current_stage="MANUAL_REVIEW",
                status="OPEN",
            )

        return updated_count

    @classmethod
    def confirm_resolution(cls, case_id):
        """
        Record customer confirmation of the recommendation.

        This method does not create a department task.
        """

        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        complaint = cls.get_by_case(
            normalized_case_id
        )

        if not complaint:
            raise ValueError(
                f"Complaint not found for Case ID: "
                f"{normalized_case_id}"
            )

        resolution_type = _normalize_status(
            complaint.get("resolution_type")
        )

        resolution_status = _normalize_status(
            complaint.get("resolution_status")
        )

        awaiting_confirmation = _is_true(
            complaint.get(
                "awaiting_resolution_confirmation"
            )
        )

        if resolution_type not in {
            "RETURN",
            "REFUND",
            "REPLACEMENT",
        }:
            raise ValueError(
                "No valid resolution recommendation exists."
            )

        if resolution_status != "RECOMMENDED":
            raise ValueError(
                "The complaint is not waiting for "
                "resolution confirmation."
            )

        if not awaiting_confirmation:
            raise ValueError(
                "Resolution confirmation is not pending."
            )

        updated_count = cls.update(
            {"case_id": normalized_case_id},
            {
                "resolution_status": "CONFIRMED",
                "awaiting_resolution_confirmation": "False",
                "customer_resolution_confirmed": "True",
                "complaint_status": "RESOLUTION_CONFIRMED",
                "updated_at": _now(),
            },
        )

        if updated_count:
            CaseRepository.update_stage(
                case_id=normalized_case_id,
                current_stage="RESOLUTION_CONFIRMED",
                status="OPEN",
            )

        logger.info(
            "Resolution confirmed. Case ID=%s, "
            "Resolution=%s, Updated=%s",
            normalized_case_id,
            resolution_type,
            updated_count,
        )

        return updated_count

    @classmethod
    def decline_resolution(cls, case_id):
        """
        Record that the customer declined the recommendation.
        """

        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        complaint = cls.get_by_case(
            normalized_case_id
        )

        if not complaint:
            raise ValueError(
                f"Complaint not found for Case ID: "
                f"{normalized_case_id}"
            )

        updated_count = cls.update(
            {"case_id": normalized_case_id},
            {
                "resolution_status": "DECLINED",
                "awaiting_resolution_confirmation": "False",
                "customer_resolution_confirmed": "False",
                "assigned_department": "",
                "department_task_id": "",
                "complaint_status": "AWAITING_CASE_MANAGER",
                "updated_at": _now(),
            },
        )

        if updated_count:
            CaseRepository.update_stage(
                case_id=normalized_case_id,
                current_stage="CASE_MANAGER_REVIEW",
                status="OPEN",
            )

        return updated_count

    @classmethod
    def assign_department_task(
        cls,
        case_id,
        department,
        department_task_id,
    ):
        """
        Link a confirmed complaint to a department task.
        """

        normalized_case_id = _normalize_id(case_id)
        normalized_department = _normalize_status(department)
        normalized_task_id = _normalize_id(
            department_task_id
        )

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        if not normalized_department:
            raise ValueError(
                "Department is required."
            )

        if not normalized_task_id:
            raise ValueError(
                "Department Task ID is required."
            )

        complaint = cls.get_by_case(
            normalized_case_id
        )

        if not complaint:
            raise ValueError(
                f"Complaint not found for Case ID: "
                f"{normalized_case_id}"
            )

        if not _is_true(
            complaint.get(
                "customer_resolution_confirmed"
            )
        ):
            raise ValueError(
                "A department task cannot be assigned before "
                "the customer confirms the resolution."
            )

        updated_count = cls.update(
            {"case_id": normalized_case_id},
            {
                "assigned_department": normalized_department,
                "department_task_id": normalized_task_id,
                "resolution_status": "PROCESSING",
                "complaint_status": "DEPARTMENT_PROCESSING",
                "updated_at": _now(),
            },
        )

        if updated_count:
            CaseRepository.update_stage(
                case_id=normalized_case_id,
                current_stage="DEPARTMENT_PROCESSING",
                status="OPEN",
            )

        return updated_count

    @classmethod
    def update_evidence_status(
        cls,
        case_id,
        evidence_status,
    ):
        """
        Update complaint evidence status.
        """

        normalized_case_id = _normalize_id(case_id)
        normalized_evidence_status = _normalize_status(
            evidence_status
        )

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        valid_statuses = {
            "NOT_REQUIRED",
            "NOT_SUBMITTED",
            "UPLOADED",
            "PENDING",
            "PENDING_REVIEW",
            "UNDER_REVIEW",
            "APPROVED",
            "REJECTED",
            "INVALID",
        }

        if normalized_evidence_status not in valid_statuses:
            raise ValueError(
                f"Invalid evidence status: "
                f"{normalized_evidence_status}"
            )

        updates = {
            "evidence_status": normalized_evidence_status,
            "updated_at": _now(),
        }

        if normalized_evidence_status == "NOT_SUBMITTED":
            updates["complaint_status"] = (
                "AWAITING_EVIDENCE"
            )

        elif normalized_evidence_status in {
            "UPLOADED",
            "PENDING",
            "PENDING_REVIEW",
            "UNDER_REVIEW",
        }:
            updates["complaint_status"] = (
                "AWAITING_EVIDENCE_REVIEW"
            )

        elif normalized_evidence_status == "APPROVED":
            updates["complaint_status"] = (
                "EVIDENCE_APPROVED"
            )

        elif normalized_evidence_status in {
            "REJECTED",
            "INVALID",
        }:
            updates["complaint_status"] = (
                "AWAITING_CUSTOMER"
            )

        updated_count = cls.update(
            {"case_id": normalized_case_id},
            updates,
        )

        logger.info(
            "Evidence status updated. Case ID=%s, "
            "Status=%s, Updated=%s",
            normalized_case_id,
            normalized_evidence_status,
            updated_count,
        )

        return updated_count

    @classmethod
    def update_complaint_status(
        cls,
        case_id,
        complaint_status,
    ):
        """
        Update the overall complaint status.
        """

        normalized_case_id = _normalize_id(case_id)
        normalized_status = _normalize_status(
            complaint_status
        )

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        if not normalized_status:
            raise ValueError(
                "Complaint status is required."
            )

        return cls.update(
            {"case_id": normalized_case_id},
            {
                "complaint_status": normalized_status,
                "updated_at": _now(),
            },
        )

    @classmethod
    def update_resolution(
        cls,
        case_id,
        resolution_type,
        resolution_status,
        resolution_reason="",
    ):
        """
        Update complaint resolution information.
        """

        normalized_case_id = _normalize_id(case_id)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        return cls.update(
            {"case_id": normalized_case_id},
            {
                "resolution_type": _normalize_status(
                    resolution_type
                ),
                "resolution_status": _normalize_status(
                    resolution_status
                ),
                "resolution_reason": _normalize_text(
                    resolution_reason
                ),
                "updated_at": _now(),
            },
        )


# =========================================================
# COMPLAINT ACTION REPOSITORY
# =========================================================

class ComplaintActionRepository(BaseRepository):
    FILE = COMPLAINT_ACTIONS_FILE

    @classmethod
    def create_action(
        cls,
        case_id,
        order_id,
        action_type,
        action_status="PENDING",
        details="",
    ):
        action_id = (
            f"ACT{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "action_id": action_id,
            "case_id": _normalize_id(case_id),
            "order_id": _normalize_id(order_id),
            "action_type": _normalize_status(action_type),
            "action_status": _normalize_status(
                action_status or "PENDING"
            ),
            "details": _normalize_text(details),
            "created_at": _now(),
        }

        return cls.create(row)

    @classmethod
    def for_case(cls, case_id):
        return cls.find_by(
            case_id=_normalize_id(case_id)
        )


# =========================================================
# ENQUIRY REPOSITORY
# =========================================================

class EnquiryRepository(BaseRepository):
    FILE = ENQUIRIES_FILE

    @classmethod
    def create_enquiry(
        cls,
        case_id,
        customer_id,
        query,
        answer="",
        sources=None,
        escalated=False,
    ):
        enquiry_id = (
            f"ENQ{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "enquiry_id": enquiry_id,
            "case_id": _normalize_id(case_id),
            "customer_id": _normalize_id(customer_id),
            "query": _normalize_text(query),
            "answer": _normalize_text(answer),
            "sources": "; ".join(
                str(source)
                for source in (sources or [])
                if source
            ),
            "escalated": str(bool(escalated)),
        }

        cls.create(row)

        return row

    @classmethod
    def get_by_id(cls, enquiry_id):
        return cls.get(
            enquiry_id=_normalize_id(enquiry_id)
        )

    @classmethod
    def get_by_customer(cls, customer_id):
        return cls.find_by(
            customer_id=_normalize_id(customer_id)
        )


# =========================================================
# EVIDENCE REPOSITORY
# =========================================================

class EvidenceRepository(BaseRepository):
    """
    Repository for customer-uploaded complaint evidence.
    """

    FILE = EVIDENCE_REVIEWS_FILE

    @classmethod
    def create_pending(
        cls,
        case_id,
        order_id,
        file_path,
        evidence_type="IMAGE",
        description="Customer uploaded complaint evidence",
    ):
        normalized_case_id = _normalize_id(case_id)
        normalized_order_id = _normalize_id(order_id)
        normalized_file_path = _normalize_text(file_path)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required to create evidence."
            )

        if not normalized_order_id:
            raise ValueError(
                "Order ID is required to create evidence."
            )

        if not normalized_file_path:
            raise ValueError(
                "Evidence file path is required."
            )

        evidence_id = (
            f"EV{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "evidence_id": evidence_id,
            "case_id": normalized_case_id,
            "order_id": normalized_order_id,
            "evidence_type": _normalize_status(
                evidence_type or "IMAGE"
            ),
            "file_path": normalized_file_path,
            "description": _normalize_text(description),
            "result": "PENDING",
            "comments": "",
            "reviewed_by": "",
            "uploaded_at": _now(),
            "reviewed_at": "",
        }

        cls.create(row)

        ComplaintRepository.update_evidence_status(
            case_id=normalized_case_id,
            evidence_status="PENDING_REVIEW",
        )

        return row

    @classmethod
    def get_by_id(cls, evidence_id):
        normalized_evidence_id = _normalize_id(
            evidence_id
        )

        if not normalized_evidence_id:
            return None

        return cls.get(
            evidence_id=normalized_evidence_id
        )

    @classmethod
    def pending(cls):
        rows = cls.all()

        if rows.empty:
            return rows

        if "result" not in rows.columns:
            logger.error(
                "Column 'result' is missing from "
                "evidence_reviews.csv"
            )
            return rows.iloc[0:0]

        return rows[
            rows["result"]
            .astype(str)
            .str.strip()
            .str.upper()
            == "PENDING"
        ].copy()

    @classmethod
    def latest_for_case(cls, case_id):
        rows = cls.find_by(
            case_id=_normalize_id(case_id)
        )

        if rows.empty:
            return None

        rows = rows.copy()

        rows["_uploaded_at"] = pd.to_datetime(
            rows["uploaded_at"],
            errors="coerce",
        )

        rows = rows.sort_values(
            by="_uploaded_at",
            ascending=False,
            na_position="last",
        )

        evidence = rows.iloc[0].to_dict()
        evidence.pop("_uploaded_at", None)

        return evidence

    @classmethod
    def record_decision(
        cls,
        evidence_id,
        result,
        comments="",
        reviewed_by="",
    ):
        """
        Record human approval or rejection.

        Approval moves the complaint to EVIDENCE_APPROVED.
        It does not directly escalate to a department.
        """

        normalized_evidence_id = _normalize_id(
            evidence_id
        )
        normalized_result = _normalize_status(result)
        normalized_comments = _normalize_text(comments)
        normalized_reviewer = _normalize_text(reviewed_by)

        if not normalized_evidence_id:
            raise ValueError(
                "Evidence ID is required."
            )

        if normalized_result not in {
            "APPROVED",
            "REJECTED",
        }:
            raise ValueError(
                "Evidence result must be APPROVED or REJECTED."
            )

        if not normalized_reviewer:
            raise ValueError(
                "Reviewer name is required."
            )

        evidence = cls.get_by_id(
            normalized_evidence_id
        )

        if not evidence:
            raise ValueError(
                f"Evidence record not found: "
                f"{normalized_evidence_id}"
            )

        case_id = _normalize_id(
            evidence.get("case_id")
        )
        order_id = _normalize_id(
            evidence.get("order_id")
        )

        if not case_id:
            raise ValueError(
                "Case ID is missing from the evidence record."
            )

        updated_count = cls.update(
            {"evidence_id": normalized_evidence_id},
            {
                "result": normalized_result,
                "comments": normalized_comments,
                "reviewed_by": normalized_reviewer,
                "reviewed_at": _now(),
            },
        )

        if updated_count == 0:
            return 0

        ComplaintRepository.update_evidence_status(
            case_id=case_id,
            evidence_status=normalized_result,
        )

        if normalized_result == "APPROVED":
            CaseRepository.update_stage(
                case_id=case_id,
                current_stage="EVIDENCE_APPROVED",
                status="OPEN",
            )

            logger.info(
                "Evidence approved. Resolution recommendation "
                "is now required. Evidence ID=%s, Case ID=%s, "
                "Order ID=%s",
                normalized_evidence_id,
                case_id,
                order_id,
            )

        else:
            CaseRepository.update_stage(
                case_id=case_id,
                current_stage="AWAITING_CUSTOMER_EVIDENCE",
                status="OPEN",
            )

        return updated_count


# =========================================================
# GENERAL HITL REVIEW REPOSITORY
# =========================================================

class HitlReviewRepository(BaseRepository):
    FILE = HITL_REVIEWS_FILE

    @classmethod
    def create_review(cls, query):
        review_id = (
            f"HR-{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "review_id": review_id,
            "query": _normalize_text(query),
            "status": "PENDING",
            "human_response": "",
        }

        cls.create(row)

        return review_id

    @classmethod
    def resolve(
        cls,
        review_id,
        human_response,
    ):
        return cls.update(
            {"review_id": _normalize_id(review_id)},
            {
                "status": "RESOLVED",
                "human_response": _normalize_text(
                    human_response
                ),
            },
        )

    @classmethod
    def pending(cls):
        return cls.find_by(status="PENDING")


# =========================================================
# DEPARTMENT TASK REPOSITORY
# =========================================================

class DepartmentTaskRepository(BaseRepository):
    FILE = DEPARTMENT_TASKS_FILE

    @classmethod
    def create_task(
        cls,
        case_id,
        department,
        action,
        resolution,
        status="PENDING",
        notes="",
    ):
        """
        Create one department task per complaint case.
        """

        normalized_case_id = _normalize_id(case_id)
        normalized_department = _normalize_status(department)
        normalized_resolution = _normalize_status(resolution)

        if not normalized_case_id:
            raise ValueError(
                "Case ID is required."
            )

        existing_rows = cls.find_by(
            case_id=normalized_case_id
        )

        if not existing_rows.empty:
            active_rows = existing_rows[
                ~existing_rows["status"]
                .astype(str)
                .str.strip()
                .str.upper()
                .isin(
                    {
                        "COMPLETED",
                        "CANCELLED",
                        "REJECTED",
                    }
                )
            ]

            if not active_rows.empty:
                return active_rows.iloc[0].to_dict()

        task_id = (
            f"TASK{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "task_id": task_id,
            "case_id": normalized_case_id,
            "department": normalized_department,
            "action": _normalize_text(action),
            "resolution": normalized_resolution,
            "status": _normalize_status(
                status or "PENDING"
            ),
            "notes": _normalize_text(notes),
            "created_date": _now(),
        }

        cls.create(row)

        return row

    @classmethod
    def update_status(
        cls,
        task_id,
        status,
        notes="",
    ):
        return cls.update(
            {"task_id": _normalize_id(task_id)},
            {
                "status": _normalize_status(status),
                "notes": _normalize_text(notes),
            },
        )

    @classmethod
    def pending_for_department(
        cls,
        department,
    ):
        return cls.find_by(
            department=_normalize_status(department),
            status="PENDING",
        )


# =========================================================
# NOTIFICATION REPOSITORY
# =========================================================

class NotificationRepository(BaseRepository):
    FILE = NOTIFICATIONS_FILE

    @classmethod
    def create_notification(
        cls,
        case_id,
        customer_id,
        message,
    ):
        notification_id = (
            f"NOTIF{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "notification_id": notification_id,
            "case_id": _normalize_id(case_id),
            "customer_id": _normalize_id(customer_id),
            "message": _normalize_text(message),
            "timestamp": _now(),
        }

        return cls.create(row)

    @classmethod
    def for_case(cls, case_id):
        return cls.find_by(
            case_id=_normalize_id(case_id)
        )


# =========================================================
# REFUND REPOSITORY
# =========================================================

class RefundRepository(BaseRepository):
    FILE = REFUNDS_FILE

    @classmethod
    def has_active_refund(cls, order_id):
        rows = cls.find_by(
            order_id=_normalize_id(order_id)
        )

        if rows.empty:
            return False

        return bool(
            (
                rows["status"]
                .astype(str)
                .str.strip()
                .str.upper()
                .isin(
                    {
                        "INITIATED",
                        "PENDING",
                        "APPROVED",
                        "PROCESSING",
                    }
                )
            ).any()
        )

    @classmethod
    def create_refund(
        cls,
        case_id,
        order_id,
        customer_id,
        amount,
        status="INITIATED",
    ):
        refund_id = (
            f"REF{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "refund_id": refund_id,
            "case_id": _normalize_id(case_id),
            "order_id": _normalize_id(order_id),
            "customer_id": _normalize_id(customer_id),
            "amount": _normalize_text(amount),
            "status": _normalize_status(status),
            "refund_date": _today(),
        }

        return cls.create(row)


# =========================================================
# REPLACEMENT REPOSITORY
# =========================================================

class ReplacementRepository(BaseRepository):
    FILE = REPLACEMENTS_FILE

    @classmethod
    def has_active_replacement(cls, order_id):
        rows = cls.find_by(
            order_id=_normalize_id(order_id)
        )

        if rows.empty:
            return False

        return bool(
            (
                rows["status"]
                .astype(str)
                .str.strip()
                .str.upper()
                .isin(
                    {
                        "INITIATED",
                        "PENDING",
                        "APPROVED",
                        "PROCESSING",
                        "DISPATCHED",
                    }
                )
            ).any()
        )

    @classmethod
    def create_replacement(
        cls,
        case_id,
        order_id,
        customer_id,
        status="INITIATED",
    ):
        replacement_id = (
            f"REP{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "replacement_id": replacement_id,
            "case_id": _normalize_id(case_id),
            "order_id": _normalize_id(order_id),
            "customer_id": _normalize_id(customer_id),
            "status": _normalize_status(status),
            "replacement_date": _today(),
        }

        return cls.create(row)


# =========================================================
# VOUCHER REPOSITORY
# =========================================================

class VoucherRepository(BaseRepository):
    FILE = VOUCHERS_FILE

    @classmethod
    def has_previous_voucher(
        cls,
        customer_id,
    ):
        rows = cls.find_by(
            customer_id=_normalize_id(customer_id)
        )

        return not rows.empty

    @classmethod
    def create_voucher(
        cls,
        case_id,
        customer_id,
        amount,
        status="ISSUED",
    ):
        voucher_id = (
            f"VOC{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "voucher_id": voucher_id,
            "case_id": _normalize_id(case_id),
            "customer_id": _normalize_id(customer_id),
            "amount": _normalize_text(amount),
            "status": _normalize_status(status),
            "issued_date": _today(),
        }

        return cls.create(row)


# =========================================================
# AUDIT REPOSITORY
# =========================================================

class AuditRepository(BaseRepository):
    FILE = AUDIT_LOGS_FILE

    @classmethod
    def log(
        cls,
        case_id,
        action,
        user="System",
    ):
        log_id = (
            f"LOG{uuid.uuid4().hex[:8].upper()}"
        )

        row = {
            "log_id": log_id,
            "case_id": _normalize_id(case_id),
            "timestamp": _now(),
            "action": _normalize_text(action),
            "user": _normalize_text(user or "System"),
        }

        return cls.create(row)

    @classmethod
    def for_case(cls, case_id):
        return cls.find_by(
            case_id=_normalize_id(case_id)
        )