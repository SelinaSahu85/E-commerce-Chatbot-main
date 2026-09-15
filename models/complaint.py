from typing import Optional
from pydantic import BaseModel


class Complaint(BaseModel):

    case_id: str
    customer_id: str
    order_id: str
    product_id: Optional[str] = ""
    complaint_type: str
    complaint_text: str
    requested_resolution: Optional[str] = ""
    evidence_required: Optional[str] = "No"
    recommended_resolution: Optional[str] = ""


class EvidenceReview(BaseModel):

    evidence_id: str
    case_id: str
    result: Optional[str] = "Pending"
    comments: Optional[str] = ""
    reviewed_by: Optional[str] = ""
