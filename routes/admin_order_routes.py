from flask import Blueprint, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Order, OrderItem, OrderStatusHistory, Product
from services.auth_service import api_admin_required
from services.audit_service import record_admin_action
from services.notification_service import create_order_status_notification

admin_order_bp = Blueprint(
    "admin_orders",
    __name__,
    url_prefix="/api/v1/admin/orders",
)

ORDER_STATUSES = [
    "placed",
    "confirmed",
    "stock_reserved",
    "picking_assigned",
    "picking",
    "picked",
    "packing",
    "ready_for_dispatch",
    "delivery_assigned",
    "picked_up",
    "out_for_delivery",
    "delivered",
    "cancelled",
]

ALLOWED_TRANSITIONS = {
    "placed": {"confirmed", "cancelled"},
    "confirmed": {"stock_reserved", "cancelled"},
    "stock_reserved": {"picking_assigned", "cancelled"},
    "picking_assigned": {"picking", "cancelled"},
    "picking": {"picked", "cancelled"},
    "picked": {"packing"},
    "packing": {"ready_for_dispatch"},
    "ready_for_dispatch": {"delivery_assigned"},
    "delivery_assigned": {"picked_up"},
    "picked_up": {"out_for_delivery"},
    "out_for_delivery": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
}


def order_payload(order):
    return {
        "id": order.id,
        "order_number": order.order_number,
        "user_id": order.user_id,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_paise": order.total_paise,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity": item.quantity,
                "unit_price_paise": item.unit_price_paise,
                "subtotal_paise": item.quantity * item.unit_price_paise,
            }
            for item in order.items
        ],
    }


@admin_order_bp.get("/")
@api_admin_required
def list_orders():
    status = request.args.get("status", "").strip().lower()
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if page < 1 or per_page < 1 or per_page > 100:
        return jsonify({"error": "Invalid pagination values."}), 400

    query = Order.query

    if status:
        if status not in ORDER_STATUSES:
            return jsonify({"error": "Invalid order status."}), 400
        query = query.filter_by(status=status)

    pagination = query.order_by(Order.id.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        "items": [order_payload(order) for order in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


@admin_order_bp.get("/<int:order_id>")
@api_admin_required
def get_order(order_id):
    order = db.session.get(Order, order_id)

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    return jsonify({"order": order_payload(order)})


@admin_order_bp.patch("/<int:order_id>/status")
@api_admin_required
def update_order_status(order_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")

    if not isinstance(new_status, str):
        return jsonify({"error": "A new status is required."}), 400

    new_status = new_status.strip().lower()

    if new_status not in ORDER_STATUSES:
        return jsonify({"error": "Invalid order status."}), 400

    order = db.session.execute(
        select(Order)
        .where(Order.id == order_id)
        .with_for_update()
    ).scalar_one_or_none()

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    if new_status == order.status:
        return jsonify({
            "message": "Order already has this status.",
            "status": order.status,
        })

    allowed = ALLOWED_TRANSITIONS.get(order.status, set())

    if new_status not in allowed:
        return jsonify({
            "error": "This order status transition is not allowed.",
            "current_status": order.status,
            "allowed_next_statuses": sorted(allowed),
        }), 409

    try:
        if new_status == "cancelled":
            items = db.session.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            ).scalars().all()

            for item in items:
                product = db.session.execute(
                    select(Product)
                    .where(Product.id == item.product_id)
                    .with_for_update()
                ).scalar_one_or_none()

                if product is not None:
                    product.stock_quantity += item.quantity

        old_status = order.status
        order.status = new_status
        create_order_status_notification(order)

        db.session.add(OrderStatusHistory(
            order_id=order.id,
            status=new_status,
            note=f"Status changed from {old_status} to {new_status}.",
            changed_by_user_id=None,
        ))

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Unable to update order status."
        }), 500

    return jsonify({
        "message": "Order status and timeline updated.",
        "order_id": order.id,
        "previous_status": old_status,
        "status": new_status,
    })
