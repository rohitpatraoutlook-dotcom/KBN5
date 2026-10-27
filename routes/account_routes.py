from flask import Blueprint, g, jsonify, request
from flask_login import logout_user

from extensions import db
from models import CartItem
from services.auth_service import api_login_required

account_bp = Blueprint(
    "account",
    __name__,
    url_prefix="/api/v1/account",
)


@account_bp.post("/deactivate")
@api_login_required
def deactivate_account():
    data = request.get_json(silent=True) or {}
    password = data.get("password")

    if not isinstance(password, str) or not password:
        return jsonify({
            "error": "Your current password is required."
        }), 400

    user = g.kbn5_user

    if not user.check_password(password):
        return jsonify({"error": "Password is incorrect."}), 401

    if user.role == "admin":
        return jsonify({
            "error": "Administrator accounts cannot be deactivated here."
        }), 403

    try:
        # Deactivate the account so it cannot authenticate again.
        user.is_active = False

        # Remove unsubmitted cart items; preserve orders and payment records.
        CartItem.query.filter_by(user_id=user.id).delete(
            synchronize_session=False
        )

        db.session.commit()
        logout_user()

        return jsonify({
            "message": (
                "Account deactivated. Sign-in is disabled. "
                "Contact KBN5 support if you need account reactivation."
            )
        })
    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Could not deactivate the account."
        }), 500
