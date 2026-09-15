from utils.logger import logger


def fallback_evidence_message(
    customer_name,
    product_name,
    case_id,
    complaint_status,
):
    return (
        f"Thank you, {customer_name}. I found your complaint "
        f"for **{product_name}**.\n\n"
        f"Your case ID is **{case_id}**, and the current status is "
        f"**{complaint_status}**.\n\n"
        "To help our review team verify the reported damage, "
        "please upload a clear image of the item. Once uploaded, "
        "the image will be sent to a customer-care reviewer for "
        "approval."
    )


def generate_evidence_request(
    llm,
    customer,
    order,
    complaint,
):
    """
    Use the LLM only to improve wording.

    Evidence requirement and HITL routing are decided by application rules.
    """

    customer_name = customer.get(
        "customer_name",
        "Customer",
    )

    product_name = order.get(
        "product_name",
        "your product",
    )

    case_id = complaint.get(
        "case_id",
        "N/A",
    )

    complaint_status = complaint.get(
        "complaint_status",
        "OPEN",
    )

    fallback = fallback_evidence_message(
        customer_name=customer_name,
        product_name=product_name,
        case_id=case_id,
        complaint_status=complaint_status,
    )

    if llm is None:
        return fallback

    prompt = f"""
You are an e-commerce customer support assistant.

Write a brief and empathetic response to the customer.

Customer name: {customer_name}
Product: {product_name}
Case ID: {case_id}
Complaint status: {complaint_status}
Issue type: {complaint.get("issue_type", "")}
Evidence status: {complaint.get("evidence_status", "")}

Instructions:
1. Confirm that the complaint is still being reviewed.
2. Explain that a clear product image is required.
3. Ask the customer to upload the image.
4. Explain that a human customer-care reviewer will approve or reject it.
5. Do not promise a refund or replacement.
6. Use at most 100 words.
"""

    try:
        result = llm.invoke(prompt)

        if hasattr(result, "content"):
            response = str(result.content).strip()
        else:
            response = str(result).strip()

        return response or fallback

    except Exception as exc:
        logger.exception(
            "LLM complaint response generation failed: %s",
            exc,
        )

        return fallback