# import os
# import pandas as pd

# from config.setting import TRANSACTION_DATA_DIR, MASTER_DATA_DIR


# def read_csv(path):
#     """
#     Read a CSV as a DataFrame. Returns an empty DataFrame with no
#     columns if the file does not exist yet (caller should check schema).
#     """

#     if not os.path.exists(path):
#         return pd.DataFrame()

#     return pd.read_csv(path, dtype=str).fillna("")


# def write_csv(path, df):
#     """
#     Atomically write a DataFrame to CSV (write to temp file, then rename)
#     to avoid corrupting the file if the process is interrupted mid-write.
#     """

#     os.makedirs(os.path.dirname(path), exist_ok=True)

#     tmp_path = f"{path}.tmp"

#     df.to_csv(tmp_path, index=False)

#     os.replace(tmp_path, path)


# def append_row(path, columns, row: dict):
#     """
#     Append a single row (dict) to a CSV, creating it with the given
#     columns if it doesn't exist yet.
#     """

#     df = read_csv(path)

#     if df.empty:
#         df = pd.DataFrame(columns=columns)

#     row_df = pd.DataFrame([{col: str(row.get(col, "")) for col in columns}])

#     df = pd.concat([df, row_df], ignore_index=True)

#     write_csv(path, df)


# def update_rows(path, columns, match: dict, updates: dict):
#     """
#     Update all rows matching `match` (column -> value) with `updates`
#     (column -> value). Returns the number of rows updated.
#     """

#     df = read_csv(path)

#     if df.empty:
#         return 0

#     mask = pd.Series([True] * len(df))

#     for col, val in match.items():
#         mask &= (df[col].astype(str) == str(val))

#     updated = int(mask.sum())

#     for col, val in updates.items():
#         df.loc[mask, col] = str(val)

#     write_csv(path, df)

#     return updated


# # --- Transaction data (mutable, case-lifecycle CSVs) ---

# CUSTOMERS_FILE = MASTER_DATA_DIR / "customers.csv"
# ORDERS_FILE = TRANSACTION_DATA_DIR / "orders.csv"
# PRODUCTS_FILE = MASTER_DATA_DIR / "products.csv"
# DEPARTMENTS_FILE = MASTER_DATA_DIR / "departments.csv"
# WORKFLOW_TRANSITIONS_FILE = MASTER_DATA_DIR / "workflow_transitions.csv"

# CASES_FILE = TRANSACTION_DATA_DIR / "cases.csv"
# COMPLAINTS_FILE = TRANSACTION_DATA_DIR / "complaints.csv"
# ENQUIRIES_FILE = TRANSACTION_DATA_DIR / "enquiries.csv"
# EVIDENCE_REVIEWS_FILE = TRANSACTION_DATA_DIR / "evidence_reviews.csv"
# HITL_REVIEWS_FILE = TRANSACTION_DATA_DIR / "hitl_reviews.csv"
# DEPARTMENT_TASKS_FILE = TRANSACTION_DATA_DIR / "department_tasks.csv"
# NOTIFICATIONS_FILE = TRANSACTION_DATA_DIR / "notifications.csv"
# REFUNDS_FILE = TRANSACTION_DATA_DIR / "refunds.csv"
# REPLACEMENTS_FILE = TRANSACTION_DATA_DIR / "replacements.csv"
# VOUCHERS_FILE = TRANSACTION_DATA_DIR / "vouchers.csv"
# AUDIT_LOGS_FILE = TRANSACTION_DATA_DIR / "audit_logs.csv"


import os
from pathlib import Path

import pandas as pd

from config.setting import (
    MASTER_DATA_DIR,
    TRANSACTION_DATA_DIR,
)


# =========================================================
# DIRECTORY PATHS
# =========================================================

# Convert configured directories to Path objects.
MASTER_DATA_PATH = Path(MASTER_DATA_DIR)

TRANSACTION_DATA_PATH = Path(TRANSACTION_DATA_DIR)


# =========================================================
# MASTER DATA FILES
# =========================================================

CUSTOMERS_FILE = (
    MASTER_DATA_PATH / "customers.csv"
)

PRODUCTS_FILE = (
    MASTER_DATA_PATH / "products.csv"
)

DEPARTMENTS_FILE = (
    MASTER_DATA_PATH / "departments.csv"
)

WORKFLOW_TRANSITIONS_FILE = (
    MASTER_DATA_PATH / "workflow_transitions.csv"
)


# =========================================================
# CONSOLIDATED COMPLAINT DATA FILES
# =========================================================

ORDERS_FILE = (
    TRANSACTION_DATA_PATH / "orders.csv"
)

COMPLAINTS_FILE = (
    TRANSACTION_DATA_PATH / "complaints.csv"
)

COMPLAINT_ACTIONS_FILE = (
    TRANSACTION_DATA_PATH / "complaint_actions.csv"
)

# =========================================================
# ENQUIRY, EVIDENCE AND HITL FILES
# =========================================================

ENQUIRIES_FILE = (
    TRANSACTION_DATA_PATH / "enquiries.csv"
)

EVIDENCE_REVIEWS_FILE = (
    TRANSACTION_DATA_PATH / "evidence_reviews.csv"
)

HITL_REVIEWS_FILE = (
    TRANSACTION_DATA_PATH / "hitl_reviews.csv"
)


# =========================================================
# EXISTING SERVICE FILES
# =========================================================

# These files are retained because the existing repositories
# and services still import them.

CASES_FILE = (
    TRANSACTION_DATA_PATH / "cases.csv"
)

DEPARTMENT_TASKS_FILE = (
    TRANSACTION_DATA_PATH / "department_tasks.csv"
)

NOTIFICATIONS_FILE = (
    TRANSACTION_DATA_PATH / "notifications.csv"
)

REFUNDS_FILE = (
    TRANSACTION_DATA_PATH / "refunds.csv"
)

REPLACEMENTS_FILE = (
    TRANSACTION_DATA_PATH / "replacements.csv"
)

VOUCHERS_FILE = (
    TRANSACTION_DATA_PATH / "vouchers.csv"
)

AUDIT_LOGS_FILE = (
    TRANSACTION_DATA_PATH / "audit_logs.csv"
)


# =========================================================
# READ CSV
# =========================================================

def read_csv(path):
    """
    Read a CSV file safely.

    Returns an empty DataFrame when:
    - the file does not exist
    - the file is completely empty
    - the file contains no readable CSV data
    """

    csv_path = Path(path)

    if not csv_path.exists():
        return pd.DataFrame()

    if csv_path.stat().st_size == 0:
        return pd.DataFrame()

    try:
        dataframe = pd.read_csv(
            csv_path,
            dtype=str,
            keep_default_na=False,
        )

        # Standardize column names.
        dataframe.columns = (
            dataframe.columns
            .astype(str)
            .str.replace("\ufeff", "", regex=False)
            .str.strip()
            .str.lower()
        )

        return dataframe

    except pd.errors.EmptyDataError:
        return pd.DataFrame()

    except pd.errors.ParserError as exc:
        raise ValueError(
            f"Unable to parse CSV file {csv_path}: {exc}"
        ) from exc


# =========================================================
# WRITE CSV
# =========================================================

def write_csv(path, dataframe, allow_empty=False):
    """
    Atomically write a DataFrame to a CSV file.

    The DataFrame is first written to a temporary file and
    then moved over the original file.

    By default, this function refuses to replace an existing
    populated CSV with a DataFrame containing zero rows.
    """

    csv_path = Path(path)

    if not isinstance(dataframe, pd.DataFrame):
        raise TypeError(
            "write_csv expects a pandas DataFrame."
        )

    csv_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_file_has_data = (
        csv_path.exists()
        and csv_path.stat().st_size > 0
    )

    if (
        existing_file_has_data
        and dataframe.empty
        and not allow_empty
    ):
        raise ValueError(
            "Refusing to overwrite a populated CSV "
            f"with an empty DataFrame: {csv_path}"
        )

    temporary_path = Path(
        f"{csv_path}.tmp"
    )

    try:
        dataframe.to_csv(
            temporary_path,
            index=False,
        )

        if not temporary_path.exists():
            raise RuntimeError(
                f"Temporary CSV was not created: "
                f"{temporary_path}"
            )

        os.replace(
            temporary_path,
            csv_path,
        )

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()

        raise


# =========================================================
# APPEND ONE ROW
# =========================================================

def append_row(path, columns, row):
    """
    Append one dictionary record to a CSV file.

    Existing records are retained. If the file does not exist,
    it is created using the supplied list of columns.
    """

    csv_path = Path(path)
    expected_columns = list(columns)

    if not isinstance(row, dict):
        raise TypeError(
            "append_row expects row to be a dictionary."
        )

    dataframe = read_csv(
        csv_path
    )

    # Initialize the schema only if no columns exist.
    if len(dataframe.columns) == 0:
        dataframe = pd.DataFrame(
            columns=expected_columns
        )

    missing_columns = [
        column
        for column in expected_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns in {csv_path}: "
            f"{missing_columns}"
        )

    row_data = {
        column: (
            ""
            if row.get(column) is None
            else str(row.get(column)).strip()
        )
        for column in expected_columns
    }

    row_dataframe = pd.DataFrame(
        [row_data],
        columns=expected_columns,
    )

    updated_dataframe = pd.concat(
        [
            dataframe,
            row_dataframe,
        ],
        ignore_index=True,
    )

    write_csv(
        csv_path,
        updated_dataframe,
    )


# =========================================================
# UPDATE EXISTING ROWS
# =========================================================

def update_rows(path, columns, match, updates):
    """
    Update all rows matching the supplied conditions.

    Example:

    update_rows(
        COMPLAINTS_FILE,
        columns,
        {"case_id": "CASE0001"},
        {"complaint_status": "RESOLVED"},
    )

    Returns the number of rows updated.
    """

    csv_path = Path(path)
    expected_columns = list(columns)

    if not isinstance(match, dict):
        raise TypeError(
            "update_rows expects match to be a dictionary."
        )

    if not isinstance(updates, dict):
        raise TypeError(
            "update_rows expects updates to be a dictionary."
        )

    if not match:
        raise ValueError(
            "At least one matching condition is required."
        )

    if not updates:
        return 0

    dataframe = read_csv(
        csv_path
    )

    if dataframe.empty:
        return 0

    missing_columns = [
        column
        for column in expected_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing columns in {csv_path}: "
            f"{missing_columns}"
        )

    invalid_match_columns = [
        column
        for column in match
        if column not in dataframe.columns
    ]

    if invalid_match_columns:
        raise ValueError(
            f"Invalid matching columns in {csv_path}: "
            f"{invalid_match_columns}"
        )

    invalid_update_columns = [
        column
        for column in updates
        if column not in dataframe.columns
    ]

    if invalid_update_columns:
        raise ValueError(
            f"Invalid update columns in {csv_path}: "
            f"{invalid_update_columns}"
        )

    mask = pd.Series(
        True,
        index=dataframe.index,
        dtype=bool,
    )

    for column, value in match.items():
        expected_value = str(
            value
        ).strip()

        mask &= (
            dataframe[column]
            .astype(str)
            .str.strip()
            == expected_value
        )

    updated_count = int(
        mask.sum()
    )

    if updated_count == 0:
        return 0

    for column, value in updates.items():
        dataframe.loc[mask, column] = (
            ""
            if value is None
            else str(value).strip()
        )

    write_csv(
        csv_path,
        dataframe,
    )

    return updated_count