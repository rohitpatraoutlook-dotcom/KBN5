from flask import Blueprint, jsonify, request, g

from extensions import db
from models import Notification
from services.auth_service import api_login_required

notification_center_bp = Blueprint(
    "notification_center",
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
        "read": item.is_read,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@notification_center_bp.get("/")
@api_login_required
def list_notifications():
    user_id = g.kbn5_user.id
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(50, max(1, request.args.get("per_page", 20, type=int)))

    query = Notification.query.filter_by(user_id=user_id)
    unread_count = query.filter_by(is_read=False).count()

    pagination = query.order_by(
        Notification.created_at.desc(),
        Notification.id.desc(),
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        "items": [notification_payload(item) for item in pagination.items],
        "unread_count": unread_count,
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


@notification_center_bp.get("/unread-count")
@api_login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=g.kbn5_user.id,
        is_read=False,
    ).count()

    return jsonify({"unread_count": count})


@notification_center_bp.patch("/<int:notification_id>/read")
@api_login_required
def mark_read(notification_id):
    item = Notification.query.filter_by(
        id=notification_id,
        user_id=g.kbn5_user.id,
    ).first()

    if item is None:
        return jsonify({"error": "Notification not found."}), 404

    item.is_read = True
    db.session.commit()

    return jsonify({
        "message": "Notification marked as read.",
        "notification": notification_payload(item),
    })


@notification_center_bp.post("/mark-all-read")
@api_login_required
def mark_all_read():
    updated = Notification.query.filter_by(
        user_id=g.kbn5_user.id,
        is_read=False,
    ).update(
        {Notification.is_read: True},
        synchronize_session=False,
    )

    db.session.commit()

    return jsonify({
        "message": "All notifications marked as read.",
        "updated_count": updated,
        "unread_count": 0,
    })


@notification_center_bp.delete("/<int:notification_id>")
@api_login_required
def delete_notification(notification_id):
    item = Notification.query.filter_by(
        id=notification_id,
        user_id=g.kbn5_user.id,
    ).first()

    if item is None:
        return jsonify({"error": "Notification not found."}), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({"message": "Notification deleted."})
