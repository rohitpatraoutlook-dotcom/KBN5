from datetime import datetime, timezone

from flask import Blueprint, jsonify, request, g
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Order, User, OrderStatusHistory
from services.auth_service import api_admin_required, api_login_required
from services.notification_service import create_order_status_notification

delivery_bp = Blueprint("delivery", __name__)

ACTIVE_STATUSES = {
    "delivery_assigned",
    "picked_up",
    "out_for_delivery",
}


def now_utc():
    return datetime.now(timezone.utc)


class DeliveryAssignment(db.Model):
    __tablename__ = "delivery_assignments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    delivery_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    assigned_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
    )
    status = db.Column(db.String(40), nullable=False, default="assigned")
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    location_updated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    delivery_note = db.Column(db.String(500), nullable=True)
    proof_reference = db.Column(db.String(500), nullable=True)
    delivered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=now_utc,
    )

    order = db.relationship("Order")
    delivery_user = db.relationship("User", foreign_keys=[delivery_user_id])
    assigned_by = db.relationship("User", foreign_keys=[assigned_by_user_id])


def assignment_payload(row):
    return {
        "id": row.id,
        "order_id": row.order_id,
        "order_number": row.order.order_number,
        "order_status": row.order.status,
        "delivery_user_id": row.delivery_user_id,
        "delivery_name": row.delivery_user.display_name,
        "delivery_username": row.delivery_user.username,
        "status": row.status,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "location_updated_at": (
            row.location_updated_at.isoformat()
            if row.location_updated_at else None
        ),
        "delivery_note": row.delivery_note,
        "proof_reference": row.proof_reference,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def is_assigned_driver(row):
    user = g.kbn5_user
    return row.delivery_user_id == user.id and user.role in {
        "delivery_partner", "delivery", "driver"
    }


@delivery_bp.get("/api/v1/admin/delivery-partners")
@api_admin_required
def list_delivery_partners():
    users = User.query.filter(
        User.is_active.is_(True),
        User.role.in_(["delivery_partner", "delivery", "driver"]),
    ).order_by(User.display_name.asc()).all()

    return jsonify({
        "items": [{
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
        } for user in users],
        "total": len(users),
    })


@delivery_bp.post("/api/v1/admin/deliveries/assign")
@api_admin_required
def assign_delivery():
    data = request.get_json(silent=True) or {}
    order_id = data.get("order_id")
    delivery_user_id = data.get("delivery_user_id")

    if not isinstance(order_id, int) or isinstance(order_id, bool):
        return jsonify({"error": "A valid order_id is required."}), 400

    if not isinstance(delivery_user_id, int) or isinstance(delivery_user_id, bool):
        return jsonify({"error": "A valid delivery_user_id is required."}), 400

    order = db.session.get(Order, order_id)
    driver = db.session.get(User, delivery_user_id)

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    if driver is None or not driver.is_active or driver.role not in {
        "delivery_partner", "delivery", "driver"
    }:
        return jsonify({
            "error": "Active delivery partner account not found."
        }), 400

    if order.status not in {"ready_for_dispatch", "delivery_assigned"}:
        return jsonify({
            "error": "Order must be ready for dispatch before assignment.",
            "current_status": order.status,
        }), 409

    row = DeliveryAssignment.query.filter_by(order_id=order.id).first()
    previous_status = order.status

    if row is None:
        row = DeliveryAssignment(
            order_id=order.id,
            delivery_user_id=driver.id,
            assigned_by_user_id=g.kbn5_user.id,
        )
        db.session.add(row)
    else:
        if row.status == "delivered":
            return jsonify({"error": "Delivered orders cannot be reassigned."}), 409
        row.delivery_user_id = driver.id
        row.assigned_by_user_id = g.kbn5_user.id
        row.status = "assigned"

    order.status = "delivery_assigned"

    try:
        db.session.add(OrderStatusHistory(
            order_id=order.id,
            status="delivery_assigned",
            note=f"Delivery assigned to {driver.username}.",
            changed_by_user_id=g.kbn5_user.id,
        ))
        create_order_status_notification(order)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not assign delivery partner."}), 500

    return jsonify({
        "message": "Delivery partner assigned.",
        "previous_order_status": previous_status,
        "assignment": assignment_payload(row),
    }), 201


@delivery_bp.get("/api/v1/delivery/my")
@api_login_required
def my_deliveries():
    user = g.kbn5_user
    if user.role not in {"delivery_partner", "delivery", "driver", "admin"}:
        return jsonify({"error": "Delivery partner access required."}), 403

    query = DeliveryAssignment.query

    if user.role != "admin":
        query = query.filter_by(delivery_user_id=user.id)

    status = request.args.get("status", "").strip().lower()
    if status:
        query = query.filter_by(status=status)

    rows = query.order_by(DeliveryAssignment.created_at.desc()).limit(100).all()

    return jsonify({
        "items": [assignment_payload(row) for row in rows],
        "total": len(rows),
    })


@delivery_bp.patch("/api/v1/delivery/<int:assignment_id>/location")
@api_login_required
def update_delivery_location(assignment_id):
    row = db.session.get(DeliveryAssignment, assignment_id)
    if row is None:
        return jsonify({"error": "Delivery assignment not found."}), 404

    if not is_assigned_driver(row) and g.kbn5_user.role != "admin":
        return jsonify({"error": "You cannot update this delivery."}), 403

    if row.status == "delivered":
        return jsonify({"error": "Delivery is already completed."}), 409

    data = request.get_json(silent=True) or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not isinstance(latitude, (int, float)) or isinstance(latitude, bool):
        return jsonify({"error": "latitude must be numeric."}), 400

    if not isinstance(longitude, (int, float)) or isinstance(longitude, bool):
        return jsonify({"error": "longitude must be numeric."}), 400

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({"error": "Coordinates are out of range."}), 400

    row.latitude = float(latitude)
    row.longitude = float(longitude)
    row.location_updated_at = now_utc()
    db.session.commit()

    return jsonify({
        "message": "Delivery location updated.",
        "assignment": assignment_payload(row),
    })


@delivery_bp.patch("/api/v1/delivery/<int:assignment_id>/status")
@api_login_required
def update_delivery_status(assignment_id):
    row = db.session.get(DeliveryAssignment, assignment_id)
    if row is None:
        return jsonify({"error": "Delivery assignment not found."}), 404

    if not is_assigned_driver(row) and g.kbn5_user.role != "admin":
        return jsonify({"error": "You cannot update this delivery."}), 403

    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    transitions = {
        "assigned": {"picked_up"},
        "picked_up": {"out_for_delivery"},
        "out_for_delivery": {"delivered"},
    }

    if new_status not in transitions.get(row.status, set()):
        return jsonify({
            "error": "Invalid delivery status transition.",
            "current_status": row.status,
            "allowed_next_statuses": sorted(transitions.get(row.status, set())),
        }), 409

    if new_status == "delivered":
        proof = data.get("proof_reference")
        note = data.get("delivery_note", "")

        if not isinstance(proof, str) or not proof.strip() or len(proof) > 500:
            return jsonify({
                "error": "Provide a proof_reference, such as a delivery photo URL or receipt reference."
            }), 400

        if not isinstance(note, str) or len(note) > 500:
            return jsonify({"error": "delivery_note must be at most 500 characters."}), 400

        row.proof_reference = proof.strip()
        row.delivery_note = note.strip() or None
        row.delivered_at = now_utc()
        row.order.status = "delivered"

    elif new_status == "picked_up":
        row.order.status = "picked_up"

    elif new_status == "out_for_delivery":
        row.order.status = "out_for_delivery"

    row.status = new_status

    try:
        db.session.add(OrderStatusHistory(
            order_id=row.order_id,
            status=row.order.status,
            note=f"Delivery status updated to {new_status}.",
            changed_by_user_id=g.kbn5_user.id,
        ))
        create_order_status_notification(row.order)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not update delivery status."}), 500

    return jsonify({
        "message": "Delivery status updated.",
        "assignment": assignment_payload(row),
    })


@delivery_bp.get("/api/v1/admin/deliveries/<int:assignment_id>")
@api_admin_required
def get_delivery_details(assignment_id):
    row = db.session.get(DeliveryAssignment, assignment_id)
    if row is None:
        return jsonify({"error": "Delivery assignment not found."}), 404

    return jsonify({"assignment": assignment_payload(row)})
