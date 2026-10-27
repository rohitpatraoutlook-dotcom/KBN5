from flask import Blueprint, jsonify, request, g

from extensions import db
from models import User
from services.auth_service import api_admin_required

staff_bp = Blueprint(
    "staff_management",
    __name__,
    url_prefix="/api/v1/admin/staff",
)

ALLOWED_ROLES = {
    "admin",
    "warehouse",
    "picker",
    "packer",
    "delivery_partner",
}


@staff_bp.get("/")
@api_admin_required
def list_staff():
    users = (
        User.query
        .filter(User.role.in_(sorted(ALLOWED_ROLES)))
        .order_by(User.id.desc())
        .limit(200)
        .all()
    )

    return jsonify({
        "items": [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "is_active": user.is_active,
            }
            for user in users
        ],
        "total": len(users),
    })


@staff_bp.patch("/<int:user_id>/role")
@api_admin_required
def update_staff_role(user_id):
    data = request.get_json(silent=True) or {}
    role = data.get("role")

    if role not in ALLOWED_ROLES:
        return jsonify({
            "error": "Role must be admin, warehouse, picker, packer or delivery_partner."
        }), 400

    actor = g.kbn5_user

    if actor.id == user_id and role != "admin":
        return jsonify({
            "error": "You cannot remove your own admin role."
        }), 400

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404

    user.role = role
    db.session.commit()

    return jsonify({
        "message": "Staff role updated.",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        },
    })


@staff_bp.patch("/<int:user_id>/active")
@api_admin_required
def set_staff_active(user_id):
    data = request.get_json(silent=True) or {}
    active = data.get("is_active")

    if not isinstance(active, bool):
        return jsonify({"error": "is_active must be true or false."}), 400

    actor = g.kbn5_user
    if actor.id == user_id and active is False:
        return jsonify({"error": "You cannot deactivate your own account."}), 400

    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found."}), 404

    user.is_active = active
    db.session.commit()

    return jsonify({
        "message": "Staff account updated.",
        "user_id": user.id,
        "is_active": user.is_active,
    })
