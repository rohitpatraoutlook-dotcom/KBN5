from flask import Blueprint, g, jsonify

from models import Order
from services.auth_service import api_login_required

tracking_bp = Blueprint(
    "tracking",
    __name__,
    url_prefix="/api/v1/tracking",
)


STATUS_LABELS = {
    "placed": "Order placed",
    "confirmed": "Order confirmed",
    "stock_reserved": "Items reserved",
    "picking_assigned": "Picker assigned",
    "picking": "Items being picked",
    "picked": "Items picked",
    "packing": "Order being packed",
    "ready_for_dispatch": "Ready for dispatch",
    "delivery_assigned": "Delivery assigned",
    "picked_up": "Order picked up",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "cancelled": "Order cancelled",
}


@tracking_bp.get("/<int:order_id>")
@api_login_required
def track_order(order_id):
    order = Order.query.filter_by(
        id=order_id,
        user_id=g.kbn5_user.id,
    ).first()

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    history = sorted(
        order.status_history,
        key=lambda item: (item.created_at, item.id),
    )

    return jsonify({
        "order": {
            "id": order.id,
            "order_number": order.order_number,
            "current_status": order.status,
            "current_status_label": STATUS_LABELS.get(
                order.status,
                order.status.replace("_", " ").title(),
            ),
            "payment_status": order.payment_status,
            "total_paise": order.total_paise,
        },
        "timeline": [
            {
                "status": item.status,
                "label": STATUS_LABELS.get(
                    item.status,
                    item.status.replace("_", " ").title(),
                ),
                "note": item.note,
                "created_at": item.created_at.isoformat(),
            }
            for item in history
        ],
    })
