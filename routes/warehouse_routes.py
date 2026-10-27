from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Product
from services.auth_service import api_admin_required

warehouse_bp = Blueprint(
    "warehouse",
    __name__,
    url_prefix="/api/v1/admin/warehouse",
)


def utc_now():
    return datetime.now(timezone.utc)


class WarehouseLocation(db.Model):
    __tablename__ = "warehouse_locations"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    rack_code = db.Column(db.String(40), nullable=False, default="UNASSIGNED")
    aisle = db.Column(db.String(40), nullable=True)
    bin_code = db.Column(db.String(40), nullable=True)
    minimum_stock = db.Column(db.Integer, nullable=False, default=5)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    product = db.relationship("Product")


class StockMovement(db.Model):
    __tablename__ = "warehouse_stock_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
        index=True,
    )
    changed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )
    quantity_before = db.Column(db.Integer, nullable=False)
    quantity_change = db.Column(db.Integer, nullable=False)
    quantity_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(250), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    product = db.relationship("Product")
    changed_by = db.relationship("User")


def stock_payload(product, location):
    quantity = int(product.stock_quantity or 0)
    minimum = location.minimum_stock if location else 5

    if quantity <= 0:
        status = "out_of_stock"
    elif quantity <= minimum:
        status = "low_stock"
    else:
        status = "in_stock"

    return {
        "product_id": product.id,
        "name": product.name,
        "sku": product.slug,
        "category_id": product.category_id,
        "active": product.is_active,
        "stock_quantity": quantity,
        "minimum_stock": minimum,
        "stock_status": status,
        "rack_code": location.rack_code if location else "UNASSIGNED",
        "aisle": location.aisle if location else None,
        "bin_code": location.bin_code if location else None,
        "updated_at": (
            location.updated_at.isoformat()
            if location and location.updated_at
            else None
        ),
    }


@warehouse_bp.get("/stock")
@api_admin_required
def list_stock():
    search = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "").strip().lower()

    query = Product.query
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    products = query.order_by(Product.name.asc()).limit(500).all()
    locations = {
        item.product_id: item
        for item in WarehouseLocation.query.filter(
            WarehouseLocation.product_id.in_(
                [p.id for p in products] or [-1]
            )
        ).all()
    }

    items = [stock_payload(p, locations.get(p.id)) for p in products]

    if status in {"low_stock", "out_of_stock", "in_stock"}:
        items = [item for item in items if item["stock_status"] == status]

    return jsonify({
        "items": items,
        "total": len(items),
        "statuses": {
            "in_stock": sum(i["stock_status"] == "in_stock" for i in items),
            "low_stock": sum(i["stock_status"] == "low_stock" for i in items),
            "out_of_stock": sum(i["stock_status"] == "out_of_stock" for i in items),
        },
    })


@warehouse_bp.patch("/stock/<int:product_id>/location")
@api_admin_required
def update_location(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json(silent=True) or {}
    location = WarehouseLocation.query.filter_by(product_id=product_id).first()

    if location is None:
        location = WarehouseLocation(product_id=product_id)
        db.session.add(location)

    for key, max_length in (
        ("rack_code", 40),
        ("aisle", 40),
        ("bin_code", 40),
    ):
        if key in data:
            value = data[key]
            if value is not None and not isinstance(value, str):
                return jsonify({"error": f"{key} must be text."}), 400
            value = (value or "").strip()
            if len(value) > max_length:
                return jsonify({"error": f"{key} is too long."}), 400
            setattr(location, key, value or None)

    if "rack_code" not in data and not location.rack_code:
        location.rack_code = "UNASSIGNED"

    if "minimum_stock" in data:
        minimum = data["minimum_stock"]
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
            return jsonify({"error": "minimum_stock must be a non-negative integer."}), 400
        location.minimum_stock = minimum

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not save warehouse location."}), 409

    return jsonify({
        "message": "Warehouse location saved.",
        "item": stock_payload(product, location),
    })


@warehouse_bp.post("/stock/<int:product_id>/adjust")
@api_admin_required
def adjust_stock(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json(silent=True) or {}
    change = data.get("quantity_change")
    reason = str(data.get("reason", "")).strip()

    if not isinstance(change, int) or isinstance(change, bool) or change == 0:
        return jsonify({"error": "quantity_change must be a non-zero integer."}), 400

    if not reason or len(reason) > 250:
        return jsonify({"error": "Provide a reason (max 250 characters)."}), 400

    before = int(product.stock_quantity or 0)
    after = before + change

    if after < 0:
        return jsonify({
            "error": "Stock cannot become negative.",
            "current_stock": before,
        }), 409

    try:
        location = WarehouseLocation.query.filter_by(
            product_id=product_id
        ).first()

        if location is None:
            location = WarehouseLocation(product_id=product_id)
            db.session.add(location)

        product.stock_quantity = after

        movement = StockMovement(
            product_id=product_id,
            changed_by_user_id=getattr(
                getattr(request, "kbn5_user", None), "id", None
            ),
            quantity_before=before,
            quantity_change=change,
            quantity_after=after,
            reason=reason,
        )

        # api_admin_required may expose the authenticated user via Flask's g.
        from flask import g
        movement.changed_by_user_id = getattr(
            getattr(g, "kbn5_user", None), "id", None
        )

        db.session.add(movement)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return jsonify({
        "message": "Stock updated.",
        "product_id": product.id,
        "quantity_before": before,
        "quantity_change": change,
        "quantity_after": after,
        "stock_status": (
            "out_of_stock" if after == 0
            else "low_stock" if after <= location.minimum_stock
            else "in_stock"
        ),
    })


@warehouse_bp.get("/movements")
@api_admin_required
def list_movements():
    product_id = request.args.get("product_id", type=int)
    limit = min(100, max(1, request.args.get("limit", 50, type=int)))

    query = StockMovement.query
    if product_id is not None:
        query = query.filter_by(product_id=product_id)

    rows = query.order_by(StockMovement.created_at.desc()).limit(limit).all()

    return jsonify({
        "items": [{
            "id": row.id,
            "product_id": row.product_id,
            "product_name": row.product.name if row.product else "Unknown",
            "changed_by_user_id": row.changed_by_user_id,
            "quantity_before": row.quantity_before,
            "quantity_change": row.quantity_change,
            "quantity_after": row.quantity_after,
            "reason": row.reason,
            "created_at": row.created_at.isoformat(),
        } for row in rows],
        "total": len(rows),
    })
