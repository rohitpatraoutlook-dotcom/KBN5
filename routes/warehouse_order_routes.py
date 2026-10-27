from flask import Blueprint, jsonify, request, g
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Order, OrderItem, OrderStatusHistory
from services.auth_service import api_admin_required
from services.notification_service import create_order_status_notification

warehouse_orders_bp = Blueprint(
    "warehouse_orders",
    __name__,
    url_prefix="/api/v1/admin/warehouse/orders",
)

STAGES = {
    "picking": {"stock_reserved", "picking_assigned", "picking", "picked"},
    "packing": {"picked", "packing", "ready_for_dispatch"},
    "dispatch": {
        "ready_for_dispatch",
        "delivery_assigned",
        "picked_up",
        "out_for_delivery",
    },
    "completed": {"delivered"},
}

NEXT_STATUS = {
    "confirmed": "stock_reserved",
    "stock_reserved": "picking_assigned",
    "picking_assigned": "picking",
    "picking": "picked",
    "picked": "packing",
    "packing": "ready_for_dispatch",
    "ready_for_dispatch": "delivery_assigned",
    "delivery_assigned": "picked_up",
    "picked_up": "out_for_delivery",
    "out_for_delivery": "delivered",
}


def warehouse_order_payload(order):
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "delivery_address": order.delivery_address,
        "total_paise": order.total_paise,
        "item_count": sum(item.quantity for item in order.items),
        "items": [
            {
                "product_id": item.product_id,
                "name": item.product_name,
                "quantity": item.quantity,
                "unit_price_paise": item.unit_price_paise,
                "subtotal_paise": item.quantity * item.unit_price_paise,
                "picked": False,
            }
            for item in order.items
        ],
    }


@warehouse_orders_bp.get("/")
@api_admin_required
def order_queue():
    stage = request.args.get("stage", "all").strip().lower()
    if stage not in {"all", *STAGES.keys()}:
        return jsonify({"error": "Stage must be all, picking, packing, dispatch or completed."}), 400

    query = Order.query

    if stage != "all":
        query = query.filter(Order.status.in_(STAGES[stage]))
    else:
        query = query.filter(
            Order.status.notin_(["delivered", "cancelled"])
        )

    orders = query.order_by(Order.created_at.asc()).limit(200).all()

    return jsonify({
        "stage": stage,
        "total": len(orders),
        "items": [warehouse_order_payload(order) for order in orders],
    })


@warehouse_orders_bp.get("/<int:order_id>/pick-list")
@api_admin_required
def pick_list(order_id):
    order = db.session.get(Order, order_id)
    if order is None:
        return jsonify({"error": "Order not found."}), 404

    return jsonify({
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "status": order.status,
            "delivery_address": order.delivery_address,
        },
        "instructions": [
            "Collect each listed item from its warehouse rack.",
            "Verify product and quantity before marking the order picked.",
            "Use the order status action to advance the workflow.",
        ],
        "items": [
            {
                "product_id": item.product_id,
                "product_name": item.product_name,
                "quantity_required": item.quantity,
                "unit_price_paise": item.unit_price_paise,
            }
            for item in order.items
        ],
    })


@warehouse_orders_bp.post("/<int:order_id>/advance")
@api_admin_required
def advance_order(order_id):
    order = db.session.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    ).scalar_one_or_none()

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    next_status = NEXT_STATUS.get(order.status)
    if not next_status:
        return jsonify({
            "error": "This order has no automatic next warehouse step.",
            "current_status": order.status,
        }), 409

    data = request.get_json(silent=True) or {}
    supplied_status = data.get("status")

    if supplied_status is not None and supplied_status != next_status:
        return jsonify({
            "error": "Invalid next status for this order.",
            "current_status": order.status,
            "expected_next_status": next_status,
        }), 409

    old_status = order.status

    try:
        order.status = next_status
        create_order_status_notification(order)

        db.session.add(OrderStatusHistory(
            order_id=order.id,
            status=next_status,
            note=f"Warehouse workflow advanced from {old_status} to {next_status}.",
            changed_by_user_id=getattr(
                getattr(g, "kbn5_user", None), "id", None
            ),
        ))

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Could not advance order workflow."}), 500

    return jsonify({
        "message": "Order workflow advanced.",
        "order_id": order.id,
        "previous_status": old_status,
        "status": next_status,
        "next_status": NEXT_STATUS.get(next_status),
    })
