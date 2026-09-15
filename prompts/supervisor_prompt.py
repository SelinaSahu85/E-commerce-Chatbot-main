INTENT_CLASSIFICATION_PROMPT = """
You are an intent classifier for an E-commerce Customer Support Assistant.

Classify the customer query into ONLY one category:

enquiry
or
complaint

Rules:

enquiry:
- return policy
- exchange policy
- shipping policy
- refund policy
- FAQs
- product information
- payment methods
- general questions

complaint:
- damaged product
- missing item
- wrong product
- refund not received
- delayed order
- defective product
- cancellation issue
- delivery issue
- customer grievance

Customer Query:
{query}

Return ONLY:
enquiry

or

complaint
"""
