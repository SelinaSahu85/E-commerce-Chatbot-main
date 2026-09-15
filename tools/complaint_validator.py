# tools/complaint_validator.py

from database.repositories import OrderRepository


def validate_complaint(order_id, issue_type, description):
    """
    Validate complaint details: required fields present and the order
    actually exists.
    """

    missing_fields = []

    if not order_id:
        missing_fields.append("Order ID")

    if not issue_type:
        missing_fields.append("Issue Type")

    if not description:
        missing_fields.append("Description")

    if missing_fields:
        return False, f"Missing fields: {', '.join(missing_fields)}"

    order = OrderRepository.get_by_id(order_id)

    if order is None:
        return False, f"Order ID '{order_id}' was not found."

    return True, "Valid complaint"
