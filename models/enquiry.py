from typing import List, Optional
from pydantic import BaseModel


class Enquiry(BaseModel):

    enquiry_id: str
    case_id: str
    customer_id: str
    query: str
    answer: Optional[str] = ""
    sources: List[str] = []
    escalated: bool = False
