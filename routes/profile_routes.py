from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash

from extensions import db
from services.auth_service import api_login_required

profile_bp = Blueprint(
    "profile",
    __name__,
    url_prefix="/api/v1/profile",
)


def profile_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }


@profile_bp.get("/")
@api_login_required
def get_profile():
    return jsonify({"user": profile_payload(g.kbn5_user)})


@profile_bp.patch("/")
@api_login_required
def update_profile():
    data = request.get_json(silent=True) or {}
    user = g.kbn5_user

    if "display_name" not in data:
        return jsonify({
            "error": "Provide display_name to update your profile."
        }), 400

    display_name = data.get("display_name")

    if not isinstance(display_name, str):
        return jsonify({"error": "Display name must be text."}), 400

    display_name = display_name.strip()

    if not display_name or len(display_name) > 120:
        return jsonify({
            "error": "Display name must be 1-120 characters."
        }), 400

    user.display_name = display_name

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update profile."}), 500

    return jsonify({
        "message": "Profile updated.",
        "user": profile_payload(user),
    })


@profile_bp.post("/change-password")
@api_login_required
def change_password():
    data = request.get_json(silent=True) or {}

    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not isinstance(current_password, str) or not isinstance(new_password, str):
        return jsonify({"error": "Both password fields are required."}), 400

    if not g.kbn5_user.check_password(current_password):
        return jsonify({"error": "Current password is incorrect."}), 401

    if not 12 <= len(new_password) <= 128:
        return jsonify({
            "error": "New password must be 12-128 characters."
        }), 400

    if current_password == new_password:
        return jsonify({
            "error": "New password must be different from current password."
        }), 400

    g.kbn5_user.set_password(new_password)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not change password."}), 500

    return jsonify({
        "message": "Password changed successfully."
    })
