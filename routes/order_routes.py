import secrets
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import (
    CartItem,
    CustomerAddress,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    ServiceableArea,
)
from services.auth_service import api_login_required

order_bp = Blueprint("orders", __name__, url_prefix="/api/v1/orders")


def order_summary(order):
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "payment_status": order.payment_status,
        "subtotal_paise": order.total_paise - order.delivery_fee_paise,
        "delivery_fee_paise": order.delivery_fee_paise,
        "total_paise": order.total_paise,
        "delivery_address": order.delivery_address,
        "created_at": order.created_at.isoformat(),
    }


@order_bp.post("/checkout")
@api_login_required
def checkout():
    data = request.get_json(silent=True) or {}
    address_id = data.get("address_id")

    if type(address_id) is not int or address_id < 1:
        return jsonify({"error": "A valid saved address_id is required."}), 400

    user_id = g.kbn5_user.id

    try:
        address = db.session.execute(
            select(CustomerAddress).where(
                CustomerAddress.id == address_id,
                CustomerAddress.user_id == user_id,
            )
        ).scalar_one_or_none()

        if address is None:
            return jsonify({"error": "Saved address not found."}), 404

        area = db.session.execute(
            select(ServiceableArea).where(
                ServiceableArea.pincode == address.pincode,
                ServiceableArea.is_active.is_(True),
            )
        ).scalar_one_or_none()

        if area is None:
            return jsonify({
                "error": "Delivery is not available at this PIN code."
            }), 409

        cart_items = db.session.execute(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .order_by(CartItem.product_id)
        ).scalars().all()

        if not cart_items:
            return jsonify({"error": "Your cart is empty."}), 400

        lines = []
        subtotal_paise = 0

        # Recheck current prices and stock at checkout.
        for cart_item in cart_items:
            product = db.session.execute(
                select(Product)
                .where(Product.id == cart_item.product_id)
                .with_for_update()
            ).scalar_one_or_none()

            if product is None or not product.is_active:
                return jsonify({
                    "error": "A product in your cart is unavailable."
                }), 409

            if (
                type(cart_item.quantity) is not int
                or cart_item.quantity < 1
                or cart_item.quantity > product.stock_quantity
            ):
                return jsonify({
                    "error": f"Insufficient stock for {product.name}."
                }), 409

            lines.append({
                "product": product,
                "quantity": cart_item.quantity,
                "unit_price_paise": product.price_paise,
                "product_name": product.name,
            })
            subtotal_paise += product.price_paise * cart_item.quantity

        if subtotal_paise < area.minimum_order_paise:
            return jsonify({
                "error": "Order total is below the area's minimum order value.",
                "subtotal_paise": subtotal_paise,
                "minimum_order_paise": area.minimum_order_paise,
            }), 409

        delivery_fee_paise = area.delivery_fee_paise
        total_paise = subtotal_paise + delivery_fee_paise

        # Save a snapshot so later address edits do not change this order.
        address_snapshot = (
            f"{address.recipient_name}, {address.phone}, "
            f"{address.address_line}"
        )
        if address.landmark:
            address_snapshot += f", Landmark: {address.landmark}"
        address_snapshot += (
            f", {address.area_name}, PIN {address.pincode}"
        )

        for line in lines:
            product = line["product"]
            quantity = line["quantity"]

            # Conditional update protects against stock changes.
            result = db.session.execute(
                select(Product)
                .where(Product.id == product.id)
                .with_for_update()
            ).scalar_one()

            if result.stock_quantity < quantity or not result.is_active:
                db.session.rollback()
                return jsonify({
                    "error": f"Stock changed for {product.name}; retry checkout."
                }), 409

            result.stock_quantity -= quantity

        order = Order(
            order_number="KBN5-" + secrets.token_hex(6).upper(),
            user_id=user_id,
            status="placed",
            payment_status="pending",
            total_paise=total_paise,
            delivery_fee_paise=delivery_fee_paise,
            delivery_address=address_snapshot,
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(order)
        db.session.flush()

        db.session.add(OrderStatusHistory(
            order_id=order.id,
            status="placed",
            note="Order placed successfully.",
            changed_by_user_id=user_id,
        ))

        for line in lines:
            db.session.add(OrderItem(
                order_id=order.id,
                product_id=line["product"].id,
                product_name=line["product_name"],
                unit_price_paise=line["unit_price_paise"],
                quantity=line["quantity"],
            ))

        for cart_item in cart_items:
            db.session.delete(cart_item)

        order_id = order.id
        order_number = order.order_number
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            "error": "Checkout could not be completed. Please retry."
        }), 500

    return jsonify({
        "message": "Order placed successfully.",
        "order": {
            "id": order_id,
            "order_number": order_number,
            "status": "placed",
            "payment_status": "pending",
            "subtotal_paise": subtotal_paise,
            "delivery_fee_paise": delivery_fee_paise,
            "total_paise": total_paise,
        },
    }), 201


@order_bp.get("/")
@api_login_required
def list_my_orders():
    orders = (
        Order.query
        .filter_by(user_id=g.kbn5_user.id)
        .order_by(Order.id.desc())
        .limit(100)
        .all()
    )

    return jsonify({
        "items": [order_summary(order) for order in orders]
    })


@order_bp.get("/<int:order_id>")
@api_login_required
def get_my_order(order_id):
    order = Order.query.filter_by(
        id=order_id,
        user_id=g.kbn5_user.id,
    ).first()

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    result = order_summary(order)
    result["items"] = [
        {
            "product_id": item.product_id,
            "product_name": item.product_name,
            "unit_price_paise": item.unit_price_paise,
            "quantity": item.quantity,
            "subtotal_paise": item.unit_price_paise * item.quantity,
        }
        for item in order.items
    ]

    return jsonify({"order": result})
