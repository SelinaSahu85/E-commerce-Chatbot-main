from typing import Any, Dict, Optional

import pandas as pd

from database.connection import (
    CUSTOMERS_FILE,
    ORDERS_FILE,
    COMPLAINTS_FILE,
)
from utils.logger import logger


def clean_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """
    Clean CSV column names and replace missing values.
    """

    cleaned_dataframe = dataframe.copy()

    cleaned_dataframe.columns = (
        cleaned_dataframe.columns
        .astype(str)
        .str.replace("\ufeff", "", regex=False)
        .str.strip()
        .str.lower()
    )

    return cleaned_dataframe.fillna("")


def normalize_id(value: Any) -> str:
    """
    Normalize identifiers such as ORD5001 and CUST001.
    """

    if value is None:
        return ""

    return str(value).strip().upper()


def load_csv(
    file_path,
    dataset_name: str
) -> Optional[pd.DataFrame]:
    """
    Load and clean a CSV dataset safely.
    """

    if not file_path.exists():
        logger.error(
            "%s dataset does not exist: %s",
            dataset_name,
            file_path,
        )
        return None

    if file_path.stat().st_size == 0:
        logger.error(
            "%s dataset is completely empty: %s",
            dataset_name,
            file_path,
        )
        return None

    try:
        dataframe = pd.read_csv(
            file_path,
            dtype=str,
            keep_default_na=False,
        )

        dataframe = clean_dataframe(
            dataframe
        )

        logger.info(
            "%s dataset loaded successfully. "
            "Rows=%s, Columns=%s",
            dataset_name,
            len(dataframe),
            list(dataframe.columns),
        )

        return dataframe

    except pd.errors.EmptyDataError:
        logger.error(
            "%s dataset has no readable data: %s",
            dataset_name,
            file_path,
        )
        return None

    except pd.errors.ParserError as exc:
        logger.exception(
            "%s dataset could not be parsed: %s",
            dataset_name,
            exc,
        )
        return None

    except Exception as exc:
        logger.exception(
            "Failed to load %s dataset: %s",
            dataset_name,
            exc,
        )
        return None


def lookup_complaint_data(
    order_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch complete complaint context using an Order ID.

    Returns:

    {
        "order": {...},
        "customer": {...},
        "complaint": {...} or None
    }

    Returns None only when the order cannot be found.
    """

    normalized_order_id = normalize_id(
        order_id
    )

    logger.info(
        "========== COMPLAINT DATA LOOKUP STARTED =========="
    )

    logger.info(
        "Requested Order ID: %s",
        normalized_order_id,
    )

    if not normalized_order_id:
        logger.warning(
            "Empty Order ID received"
        )
        return None

    # =====================================================
    # ORDER LOOKUP
    # =====================================================

    orders_dataframe = load_csv(
        file_path=ORDERS_FILE,
        dataset_name="Orders",
    )

    if orders_dataframe is None:
        return None

    if "order_id" not in orders_dataframe.columns:
        logger.error(
            "Column 'order_id' is missing from orders.csv. "
            "Available columns: %s",
            list(orders_dataframe.columns),
        )
        return None

    orders_dataframe["order_id"] = (
        orders_dataframe["order_id"]
        .apply(normalize_id)
    )

    order_match = orders_dataframe[
        orders_dataframe["order_id"]
        == normalized_order_id
    ]

    if order_match.empty:
        logger.warning(
            "Order not found: %s",
            normalized_order_id,
        )
        return None

    order = order_match.iloc[0].to_dict()

    logger.info(
        "Order found successfully: %s",
        normalized_order_id,
    )

    # =====================================================
    # CUSTOMER LOOKUP
    # =====================================================

    customer: Dict[str, Any] = {}

    customer_id = normalize_id(
        order.get("customer_id")
    )

    if not customer_id:
        logger.warning(
            "Order %s does not contain a customer_id",
            normalized_order_id,
        )

    else:
        customers_dataframe = load_csv(
            file_path=CUSTOMERS_FILE,
            dataset_name="Customers",
        )

        if customers_dataframe is not None:
            if "customer_id" not in customers_dataframe.columns:
                logger.error(
                    "Column 'customer_id' is missing from "
                    "customers.csv. Available columns: %s",
                    list(customers_dataframe.columns),
                )

            else:
                customers_dataframe["customer_id"] = (
                    customers_dataframe["customer_id"]
                    .apply(normalize_id)
                )

                customer_match = customers_dataframe[
                    customers_dataframe["customer_id"]
                    == customer_id
                ]

                if customer_match.empty:
                    logger.warning(
                        "Customer not found. "
                        "Customer ID=%s, Order ID=%s",
                        customer_id,
                        normalized_order_id,
                    )

                else:
                    customer = (
                        customer_match.iloc[0].to_dict()
                    )

                    logger.info(
                        "Customer found successfully: %s",
                        customer_id,
                    )

    # =====================================================
    # COMPLAINT LOOKUP
    # =====================================================

    complaint: Optional[Dict[str, Any]] = None

    complaints_dataframe = load_csv(
        file_path=COMPLAINTS_FILE,
        dataset_name="Complaints",
    )

    if complaints_dataframe is not None:
        if "order_id" not in complaints_dataframe.columns:
            logger.error(
                "Column 'order_id' is missing from complaints.csv. "
                "Available columns: %s",
                list(complaints_dataframe.columns),
            )

        else:
            complaints_dataframe["order_id"] = (
                complaints_dataframe["order_id"]
                .apply(normalize_id)
            )

            complaint_match = complaints_dataframe[
                complaints_dataframe["order_id"]
                == normalized_order_id
            ].copy()

            if complaint_match.empty:
                logger.info(
                    "No existing complaint found for order: %s",
                    normalized_order_id,
                )

            else:
                if "updated_at" in complaint_match.columns:
                    complaint_match["_parsed_updated_at"] = (
                        pd.to_datetime(
                            complaint_match["updated_at"],
                            errors="coerce",
                        )
                    )

                    complaint_match = complaint_match.sort_values(
                        by="_parsed_updated_at",
                        ascending=False,
                        na_position="last",
                    )

                complaint = (
                    complaint_match.iloc[0].to_dict()
                )

                complaint.pop(
                    "_parsed_updated_at",
                    None,
                )

                logger.info(
                    "Existing complaint found. "
                    "Order ID=%s, Case ID=%s, Status=%s",
                    normalized_order_id,
                    complaint.get("case_id", "N/A"),
                    complaint.get(
                        "complaint_status",
                        "N/A",
                    ),
                )

    # =====================================================
    # COMBINED RESULT
    # =====================================================

    result = {
        "order": order,
        "customer": customer,
        "complaint": complaint,
    }

    logger.info(
        "Complaint data lookup completed. "
        "Order ID=%s, Customer found=%s, "
        "Complaint found=%s",
        normalized_order_id,
        bool(customer),
        bool(complaint),
    )

    return result