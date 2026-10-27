from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from extensions import db
from models import Order, Payment
from services.auth_service import api_login_required

payment_bp = Blueprint(
    "payments",
    __name__,
    url_prefix="/api/v1/payments",
)


@payment_bp.get("/order/<int:order_id>")
@api_login_required
def get_payment(order_id):
    order = Order.query.filter_by(
        id=order_id,
        user_id=g.kbn5_user.id,
    ).first()

    if order is None:
        return jsonify({"error": "Order not found."}), 404

    payment = Payment.query.filter_by(order_id=order.id).first()

    if payment is None:
        return jsonify({
            "order_id": order.id,
            "payment_status": order.payment_status,
            "message": "Payment record has not been created yet.",
        })

    return jsonify({
        "order_id": order.id,
        "order_number": order.order_number,
        "method": payment.method,
        "status": payment.status,
        "amount_paise": payment.amount_paise,
        "provider_reference": payment.provider_reference,
        "confirmed_at": (
            payment.confirmed_at.isoformat()
            if payment.confirmed_at else None
        ),
    })


@payment_bp.post("/order/<int:order_id>/method")
@api_login_required
def choose_payment_method(order_id):
    data = request.get_json(silent=True) or {}
    method = data.get("method")

    if method not in ("cod", "online"):
        return jsonify({
            "error": "Payment method must be 'cod' or 'online'."
        }), 400

    try:
        with db.session.begin():
            order = db.session.execute(
                select(Order)
                .where(
                    Order.id == order_id,
                    Order.user_id == g.kbn5_user.id,
                )
                .with_for_update()
            ).scalar_one_or_none()

            if order is None:
                return jsonify({"error": "Order not found."}), 404

            if order.status == "cancelled":
                return jsonify({
                    "error": "Cancelled orders cannot be paid."
                }), 409

            if order.payment_status == "paid":
                return jsonify({
                    "error": "This order is already paid."
                }), 409

            payment = Payment.query.filter_by(order_id=order.id).first()

            if payment is None:
                payment = Payment(
                    order_id=order.id,
                    method=method,
                    status="pending",
                    amount_paise=order.total_paise,
                )
                db.session.add(payment)
            else:
                payment.method = method

            # Selecting online does not mean payment has been received.
            order.payment_status = "pending"

            response = {
                "order_id": order.id,
                "order_number": order.order_number,
                "method": payment.method,
                "status": payment.status,
                "amount_paise": payment.amount_paise,
            }

    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Could not update payment method."
        }), 500

    return jsonify({
        "message": "Payment method saved. No payment was collected.",
        "payment": response,
    })


@payment_bp.post("/order/<int:order_id>/cod-collected")
@api_login_required
def record_cod_collection(order_id):
    # This endpoint intentionally does not accept customer requests.
    # Collection must be confirmed through a protected operations workflow.
    if g.kbn5_user.role != "admin":
        return jsonify({
            "error": "Administrator access required."
        }), 403

    try:
        with db.session.begin():
            order = db.session.execute(
                select(Order)
                .where(Order.id == order_id)
                .with_for_update()
            ).scalar_one_or_none()

            if order is None:
                return jsonify({"error": "Order not found."}), 404

            payment = Payment.query.filter_by(order_id=order.id).first()

            if payment is None or payment.method != "cod":
                return jsonify({
                    "error": "No COD payment is configured for this order."
                }), 409

            if order.status != "delivered":
                return jsonify({
                    "error": "COD can only be recorded after delivery."
                }), 409

            if payment.status == "paid":
                return jsonify({
                    "message": "COD payment was already recorded."
                })

            payment.status = "paid"
            payment.confirmed_at = datetime.now(timezone.utc)
            order.payment_status = "paid"

    except Exception:
        db.session.rollback()
        return jsonify({
            "error": "Could not record COD payment."
        }), 500

    return jsonify({
        "message": "COD payment recorded.",
        "order_id": order_id,
        "payment_status": "paid",
    })
