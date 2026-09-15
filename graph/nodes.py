# Shared post-processing helpers usable by any graph node. Currently
# audit logging and notifications are triggered directly by the
# services/agents that need them (case_service, notification_service),
# so this module is intentionally minimal. Kept as an extension point
# for shared cross-cutting node logic (e.g. a future global guardrail
# pass on every outgoing response).

from database.schema import ensure_tables_exist


def ensure_database_ready(state):
    """
    Idempotent: makes sure all transaction CSVs exist before any agent
    node tries to read/write them.
    """

    ensure_tables_exist()

    return {}
