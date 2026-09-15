from typing import Literal, Optional
from pydantic import BaseModel

CaseType = Literal["Enquiry", "Complaint"]

CaseStatus = Literal[
    "Open",
    "In Progress",
    "Pending Customer",
    "Escalated",
    "Closed",
]


class Case(BaseModel):

    case_id: str
    customer_id: str
    order_id: Optional[str] = ""
    case_type: CaseType
    current_stage: str
    status: CaseStatus
    opened_date: str
    closed_date: Optional[str] = ""
