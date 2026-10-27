from flask import Blueprint, g, jsonify, request

from models import Order
from services.auth_service import api_login_required

customer_order_bp = Blueprint(
    "customer_orders",
    __name__,
    url_prefix="/api/v1/customer/orders",
)


def order_summary(order):
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "total_paise": order.total_paise,
        "delivery_fee_paise": order.delivery_fee_paise,
        "created_at": order.created_at.isoformat(),
        "item_count": sum(item.quantity for item in order.items),
    }


def order_detail(order):
    result = order_summary(order)
    result["delivery_address"] = order.delivery_address
    result["items"] = [
        {
            "product_id": item.product_id,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price_paise": item.unit_price_paise,
            "line_total_paise": item.quantity * item.unit_price_paise,
        }
        for item in order.items
    ]
    result["timeline"] = [
        {
            "status": event.status,
            "note": event.note,
            "created_at": event.created_at.isoformat(),
        }
        for event in sorted(
            order.status_history,
            key=lambda event: (event.created_at, event.id),
        )
    ]
    return result


@customer_order_bp.get("/")
@api_login_required
def list_customer_orders():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)

    if page < 1:
        return jsonify({"error": "Page must be at least 1."}), 400

    per_page = max(1, min(per_page, 50))

    query = Order.query.filter_by(user_id=g.kbn5_user.id)
    total = query.count()

    orders = (
        query.order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        "orders": [order_summary(order) for order in orders],
        "page": page,
        "per_page": per_page,
        "total": total,
    })


@customer_order_bp.get("/<int:order_id>")
@api_login_required
def get_customer_order(order_id):
    order = Order.query.filter_by(
        id=order_id,
        user_id=g.kbn5_user.id,
    ).first()

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    return jsonify({"order": order_detail(order)})
