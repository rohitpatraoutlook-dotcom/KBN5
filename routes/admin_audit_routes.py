from flask import Blueprint, jsonify, request

from models import AuditLog
from services.auth_service import api_admin_required

admin_audit_bp = Blueprint(
    "admin_audit",
    __name__,
    url_prefix="/api/v1/admin/audit-logs",
)


@admin_audit_bp.get("/")
@api_admin_required
def list_audit_logs():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    action = request.args.get("action", "").strip()

    if page < 1:
        return jsonify({"error": "Page must be at least 1."}), 400

    per_page = max(1, min(per_page, 100))

    query = AuditLog.query

    if action:
        query = query.filter_by(action=action)

    total = query.count()

    entries = (
        query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        "audit_logs": [
            {
                "id": entry.id,
                "actor_user_id": entry.actor_user_id,
                "action": entry.action,
                "resource_type": entry.resource_type,
                "resource_id": entry.resource_id,
                "details": entry.details,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ],
        "page": page,
        "per_page": per_page,
        "total": total,
    })
