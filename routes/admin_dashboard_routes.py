from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify
from sqlalchemy import func

from extensions import db
from models import Order, Product, User
from services.auth_service import api_admin_required

admin_dashboard_bp = Blueprint(
    "admin_dashboard",
    __name__,
    url_prefix="/api/v1/admin/dashboard",
)

@admin_dashboard_bp.get("/")
@api_admin_required
def dashboard():
    now = datetime.now(timezone.utc)
    day_start = now - timedelta(hours=24)

    total_orders = db.session.query(func.count(Order.id)).scalar() or 0

    recent_orders = (
        db.session.query(func.count(Order.id))
        .filter(Order.created_at >= day_start)
        .scalar()
        or 0
    )

    total_customers = (
        db.session.query(func.count(User.id))
        .filter(User.role == "customer")
        .scalar()
        or 0
    )

    active_products = (
        db.session.query(func.count(Product.id))
        .filter(Product.is_active.is_(True))
        .scalar()
        or 0
    )

    low_stock_products = (
        db.session.query(func.count(Product.id))
        .filter(
            Product.is_active.is_(True),
            Product.stock_quantity <= 5,
        )
        .scalar()
        or 0
    )

    status_counts = (
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )

    orders_by_status = {
        status: count for status, count in status_counts
    }

    revenue_paise = (
        db.session.query(func.coalesce(func.sum(Order.total_paise), 0))
        .filter(
            Order.payment_status == "paid",
            Order.status != "cancelled",
        )
        .scalar()
        or 0
    )

    return jsonify({
        "generated_at": now.isoformat(),
        "summary": {
            "total_orders": total_orders,
            "orders_last_24_hours": recent_orders,
            "total_customers": total_customers,
            "active_products": active_products,
            "low_stock_products": low_stock_products,
            "paid_revenue_paise": int(revenue_paise),
        },
        "orders_by_status": orders_by_status,
        "queues": {
            "awaiting_confirmation": orders_by_status.get("placed", 0),
            "awaiting_picking": (
                orders_by_status.get("stock_reserved", 0)
                + orders_by_status.get("picking_assigned", 0)
            ),
            "awaiting_packing": orders_by_status.get("picked", 0),
            "awaiting_dispatch": (
                orders_by_status.get("packing", 0)
                + orders_by_status.get("ready_for_dispatch", 0)
            ),
            "out_for_delivery": orders_by_status.get(
                "out_for_delivery", 0
            ),
        },
    })
