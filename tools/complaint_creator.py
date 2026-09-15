from database.repositories import ComplaintRepository


def create_complaint(
    case_id,
    customer_id,
    order_id,
    product_id,
    complaint_type,
    complaint_text,
    requested_resolution="",
    evidence_required="No",
):
    """
    Creates the complaint record linked to an existing case.
    """

    complaint = {
        "case_id": case_id,
        "customer_id": customer_id,
        "order_id": order_id,
        "product_id": product_id or "",
        "complaint_type": complaint_type,
        "complaint_text": complaint_text,
        "requested_resolution": requested_resolution,
        "evidence_required": evidence_required,
        "recommended_resolution": "",
    }

    ComplaintRepository.create(complaint)

    return complaint
