from flask import Blueprint, g, jsonify, request
from sqlalchemy import func

from extensions import db
from models import Notification
from services.auth_service import api_login_required

notification_bp = Blueprint(
    "notifications",
    __name__,
    url_prefix="/api/v1/notifications",
)


def notification_payload(item):
    return {
        "id": item.id,
        "title": item.title,
        "message": item.message,
        "type": item.notification_type,
        "order_id": item.related_order_id,
        "is_read": item.is_read,
        "created_at": item.created_at.isoformat(),
    }


@notification_bp.get("/")
@api_login_required
def list_notifications():
    user_id = g.kbn5_user.id

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if page < 1:
        return jsonify({"error": "Page must be at least 1."}), 400

    per_page = max(1, min(per_page, 50))

    query = Notification.query.filter_by(user_id=user_id)
    total = query.count()

    items = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    unread_count = (
        db.session.query(func.count(Notification.id))
        .filter_by(user_id=user_id, is_read=False)
        .scalar()
    )

    return jsonify({
        "notifications": [notification_payload(item) for item in items],
        "unread_count": unread_count,
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@notification_bp.patch("/<int:notification_id>/read")
@api_login_required
def mark_notification_read(notification_id):
    item = Notification.query.filter_by(
        id=notification_id,
        user_id=g.kbn5_user.id,
    ).first()

    if item is None:
        return jsonify({"error": "Notification not found."}), 404

    item.is_read = True

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update notification."}), 500

    return jsonify({
        "message": "Notification marked as read.",
        "notification": notification_payload(item),
    })


@notification_bp.post("/read-all")
@api_login_required
def mark_all_notifications_read():
    try:
        Notification.query.filter_by(
            user_id=g.kbn5_user.id,
            is_read=False,
        ).update(
            {Notification.is_read: True},
            synchronize_session=False,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update notifications."}), 500

    return jsonify({"message": "All notifications marked as read."})
