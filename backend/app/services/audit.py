import json

from flask import request
from flask_login import current_user

from ..models import AuditLog, db


def log_action(action, entity_type=None, entity_id=None, details=None, user_id=None):
    """Record an immutable audit event. Caller is responsible for db.session.commit()."""
    uid = user_id
    if uid is None:
        try:
            if current_user.is_authenticated:
                uid = current_user.id
        except RuntimeError:
            pass  # outside request context

    entry = AuditLog(
        user_id=uid,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
