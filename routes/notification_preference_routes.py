from flask import Blueprint, g, jsonify, request

from extensions import db
from models import NotificationPreference
from services.auth_service import api_login_required

preference_bp = Blueprint(
    "notification_preferences",
    __name__,
    url_prefix="/api/v1/notification-preferences",
)


def get_or_create_preferences(user_id):
    preference = NotificationPreference.query.filter_by(
        user_id=user_id
    ).first()

    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        db.session.add(preference)
        db.session.flush()

    return preference


def preference_payload(preference):
    return {
        "order_updates_enabled": preference.order_updates_enabled,
        "general_notifications_enabled": (
            preference.general_notifications_enabled
        ),
        "updated_at": preference.updated_at.isoformat(),
    }


@preference_bp.get("/")
@api_login_required
def get_preferences():
    try:
        preference = get_or_create_preferences(g.kbn5_user.id)
        db.session.commit()
        return jsonify({"preferences": preference_payload(preference)})
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not load notification preferences."}), 500


@preference_bp.patch("/")
@api_login_required
def update_preferences():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Provide at least one preference."}), 400

    allowed_fields = {
        "order_updates_enabled",
        "general_notifications_enabled",
    }

    unknown_fields = set(data) - allowed_fields
    if unknown_fields:
        return jsonify({
            "error": "Unknown preference field.",
            "allowed_fields": sorted(allowed_fields),
        }), 400

    if any(type(value) is not bool for value in data.values()):
        return jsonify({
            "error": "Preference values must be true or false."
        }), 400

    try:
        preference = get_or_create_preferences(g.kbn5_user.id)

        for field, value in data.items():
            setattr(preference, field, value)

        db.session.commit()

        return jsonify({
            "message": "Notification preferences saved.",
            "preferences": preference_payload(preference),
        })
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not save preferences."}), 500
