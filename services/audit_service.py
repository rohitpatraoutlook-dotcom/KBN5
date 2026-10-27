from extensions import db
from models import AuditLog


def record_admin_action(
    admin_id,
    action,
    resource_type,
    resource_id=None,
    details=None,
):
    """
    Add an audit entry to the current transaction.
    The caller commits or rolls back the transaction.
    Do not store passwords, tokens, or other secrets in details.
    """
    entry = AuditLog(
        actor_user_id=admin_id,
        action=action,
        resource_type=resource_type,
        resource_id=(
            str(resource_id) if resource_id is not None else None
        ),
        details=details or {},
    )
    db.session.add(entry)
    return entry
