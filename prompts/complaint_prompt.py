COMPLAINT_ANALYSIS_PROMPT = """
You are analyzing a customer complaint for an E-commerce Customer
Support System.

From the customer's message below, extract:
- complaint_type: one of DAMAGED_PRODUCT, WRONG_ITEM, MISSING_ITEM,
  REFUND_ISSUE, DELAYED_DELIVERY, DEFECTIVE_PRODUCT, OTHER
- requested_resolution: one of Refund, Replacement, Voucher, Unspecified

Customer message:
{description}

Respond in EXACTLY this format, nothing else:
complaint_type: <value>
requested_resolution: <value>
"""

RESOLUTION_EXPLANATION_PROMPT = """
You are writing a short, polite customer-facing message explaining a
complaint resolution decision for an E-commerce Customer Support System.

Resolution decided: {resolution_type}
Reason: {reason}
Policy reference: {policy_reference}

Write 2-3 sentences addressed to the customer, in plain language,
explaining the decision and the reason. Do not invent any details
beyond what is given above.
"""
