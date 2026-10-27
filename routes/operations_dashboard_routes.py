from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify
from sqlalchemy import func

from extensions import db
from models import User, Product, Order
from services.auth_service import api_admin_required

operations_dashboard_bp = Blueprint(
    "operations_dashboard",
    __name__,
    url_prefix="/api/v1/admin/operations",
)


@operations_dashboard_bp.get("/dashboard")
@api_admin_required
def operations_dashboard():
    from routes.delivery_routes import DeliveryAssignment

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=7)

    order_counts = dict(
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )

    active_orders = Order.query.filter(
        Order.status.notin_(["delivered", "cancelled"])
    ).count()

    low_stock_query = Product.query.filter(
        Product.is_active.is_(True),
        Product.stock_quantity <= 5,
    )

    low_stock_count = low_stock_query.count()

    sales_query = db.session.query(
        func.coalesce(func.sum(Order.total_paise), 0)
    ).filter(
        Order.created_at >= since,
        Order.status == "delivered",
    )

    delivered_sales_paise = int(sales_query.scalar() or 0)

    delivery_counts = dict(
        db.session.query(
            DeliveryAssignment.status,
            func.count(DeliveryAssignment.id),
        )
        .group_by(DeliveryAssignment.status)
        .all()
    )

    staff_roles = (
        db.session.query(User.role, func.count(User.id))
        .filter(User.role != "customer")
        .group_by(User.role)
        .all()
    )

    recent_orders = (
        Order.query.order_by(Order.created_at.desc())
        .limit(10)
        .all()
    )

    return jsonify({
        "generated_at": now.isoformat(),
        "summary": {
            "total_products": Product.query.filter_by(is_active=True).count(),
            "low_stock_products": low_stock_count,
            "active_orders": active_orders,
            "total_customers": User.query.filter_by(role="customer").count(),
            "staff_counts": {
                role: count for role, count in staff_roles
            },
            "delivered_sales_last_7_days_paise": delivered_sales_paise,
            "delivered_sales_last_7_days_rupees": round(
                delivered_sales_paise / 100, 2
            ),
        },
        "orders_by_status": order_counts,
        "deliveries_by_status": delivery_counts,
        "recent_orders": [
            {
                "id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
                "total_paise": order.total_paise,
                "created_at": (
                    order.created_at.isoformat()
                    if order.created_at else None
                ),
            }
            for order in recent_orders
        ],
    })


@operations_dashboard_bp.get("/health")
@api_admin_required
def operations_health():
    checks = {
        "database": False,
        "products_model": False,
        "orders_model": False,
    }

    try:
        db.session.execute(db.select(1))
        checks["database"] = True
        db.session.query(Product.id).limit(1).all()
        checks["products_model"] = True
        db.session.query(Order.id).limit(1).all()
        checks["orders_model"] = True
    except Exception:
        db.session.rollback()

    return jsonify({
        "healthy": all(checks.values()),
        "checks": checks,
    }), 200 if all(checks.values()) else 503
