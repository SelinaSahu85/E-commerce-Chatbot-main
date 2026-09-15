from typing import Literal, Optional
from pydantic import BaseModel

ResolutionType = Literal[
    "refund",
    "replacement",
    "voucher",
    "request_information",
    "request_better_evidence",
    "reject",
    "escalate",
]

# Maps a ResolutionType to the label used in datasets/master_data/workflow_transitions.csv
RESOLUTION_TO_WORKFLOW_LABEL = {
    "refund": "Refund",
    "replacement": "Replacement",
    "voucher": "Voucher",
    "request_information": "Request Missing Information",
    "request_better_evidence": "Request Better Evidence",
    "escalate": "Escalate",
}


class ResolutionRecommendation(BaseModel):

    case_id: str
    resolution_type: ResolutionType
    reason: str
    policy_reference: Optional[str] = None
