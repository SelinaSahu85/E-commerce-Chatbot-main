from database.repositories import AuditRepository


def log(case_id, action, user="System"):
    return AuditRepository.log(case_id, action, user)


def history(case_id):
    return AuditRepository.for_case(case_id)
