from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from extensions import db
from models import User
from services.auth_service import api_admin_required
from services.audit_service import record_admin_action

admin_user_bp = Blueprint(
    "admin_users",
    __name__,
    url_prefix="/api/v1/admin/users",
)


def user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
    }


@admin_user_bp.get("/")
@api_admin_required
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("q", "").strip()

    if page < 1:
        return jsonify({"error": "Page must be at least 1."}), 400

    per_page = max(1, min(per_page, 50))

    query = User.query

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
                User.display_name.ilike(term),
            )
        )

    total = query.count()

    users = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        "users": [user_payload(user) for user in users],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@admin_user_bp.get("/<int:user_id>")
@api_admin_required
def get_user(user_id):
    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({"error": "User not found."}), 404

    return jsonify({"user": user_payload(user)})


@admin_user_bp.patch("/<int:user_id>/status")
@api_admin_required
def update_user_status(user_id):
    from flask import g

    admin = g.kbn5_user
    data = request.get_json(silent=True) or {}
    is_active = data.get("is_active")

    if type(is_active) is not bool:
        return jsonify({
            "error": "is_active must be true or false."
        }), 400

    user = db.session.get(User, user_id)

    if user is None:
        return jsonify({"error": "User not found."}), 404

    if user.id == admin.id:
        return jsonify({
            "error": "You cannot change your own account status here."
        }), 400

    if user.role == "admin":
        return jsonify({
            "error": "This endpoint cannot change administrator accounts."
        }), 403

    previous_status = user.is_active
    user.is_active = is_active

    record_admin_action(
        admin_id=admin.id,
        action="customer_account_status_changed",
        resource_type="user",
        resource_id=user.id,
        details={
            "previous_is_active": previous_status,
            "new_is_active": is_active,
        },
    )

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update account status."}), 500

    return jsonify({
        "message": "Account status updated.",
        "user": user_payload(user),
    })
