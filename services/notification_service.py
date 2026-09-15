from database.repositories import NotificationRepository
from services import audit_service


def notify_customer(case_id, customer_id, message):
    """
    Records a customer-facing status update. In this MVP, notifications
    are stored and surfaced in the chat/case timeline rather than sent
    through a real channel (email/SMS).
    """

    notification = NotificationRepository.create_notification(
        case_id, customer_id, message
    )

    audit_service.log(case_id, f"Customer notified: {message}", user="System")

    return notification


def history_for_case(case_id):
    return NotificationRepository.for_case(case_id)
