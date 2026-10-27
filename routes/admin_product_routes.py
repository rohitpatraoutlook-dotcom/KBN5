import re

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Category, Product
from services.auth_service import api_admin_required
from services.audit_service import record_admin_action

admin_product_bp = Blueprint(
    "admin_products",
    __name__,
    url_prefix="/api/v1/admin/products",
)


def make_slug(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:180].strip("-")


def product_payload(product):
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "price_paise": product.price_paise,
        "stock_quantity": product.stock_quantity,
        "image_key": product.image_key,
        "category_id": product.category_id,
        "is_active": product.is_active,
    }


@admin_product_bp.post("/")
@api_admin_required
def create_product():
    data = request.get_json(silent=True) or {}

    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    price = data.get("price_paise")
    stock = data.get("stock_quantity", 0)
    category_id = data.get("category_id")

    if not name or len(name) > 160:
        return jsonify({"error": "Product name is required (max 160 characters)."}), 400

    if not isinstance(price, int) or isinstance(price, bool) or price < 0:
        return jsonify({"error": "price_paise must be a non-negative integer."}), 400

    if not isinstance(stock, int) or isinstance(stock, bool) or stock < 0:
        return jsonify({"error": "stock_quantity must be a non-negative integer."}), 400

    if category_id is not None:
        if not isinstance(category_id, int) or isinstance(category_id, bool):
            return jsonify({"error": "Invalid category_id."}), 400
        if db.session.get(Category, category_id) is None:
            return jsonify({"error": "Category not found."}), 400

    base_slug = make_slug(name)
    if not base_slug:
        return jsonify({"error": "Product name must contain letters or numbers."}), 400

    slug = base_slug
    suffix = 2
    while Product.query.filter_by(slug=slug).first() is not None:
        slug = f"{base_slug[:170]}-{suffix}"
        suffix += 1

    product = Product(
        name=name,
        slug=slug,
        description=description or None,
        price_paise=price,
        stock_quantity=stock,
        category_id=category_id,
        is_active=True,
    )

    try:
        db.session.add(product)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not save product."}), 409

    return jsonify({"product": product_payload(product)}), 201


@admin_product_bp.patch("/<int:product_id>")
@api_admin_required
def update_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify({"error": "Product not found."}), 404

    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > 160:
            return jsonify({"error": "Invalid product name."}), 400
        product.name = name

    if "description" in data:
        description = data["description"]
        if description is not None and not isinstance(description, str):
            return jsonify({"error": "Invalid description."}), 400
        product.description = description.strip() if description else None

    if "price_paise" in data:
        price = data["price_paise"]
        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            return jsonify({"error": "Invalid price_paise."}), 400
        product.price_paise = price

    if "stock_quantity" in data:
        stock = data["stock_quantity"]
        if not isinstance(stock, int) or isinstance(stock, bool) or stock < 0:
            return jsonify({"error": "Invalid stock_quantity."}), 400
        product.stock_quantity = stock

    if "category_id" in data:
        category_id = data["category_id"]
        if category_id is not None:
            if not isinstance(category_id, int) or isinstance(category_id, bool):
                return jsonify({"error": "Invalid category_id."}), 400
            if db.session.get(Category, category_id) is None:
                return jsonify({"error": "Category not found."}), 400
        product.category_id = category_id

    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return jsonify({"error": "is_active must be true or false."}), 400
        product.is_active = data["is_active"]

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not update product."}), 409

    return jsonify({"product": product_payload(product)})


@admin_product_bp.delete("/<int:product_id>")
@api_admin_required
def deactivate_product(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify({"error": "Product not found."}), 404

    # Keep historical references intact instead of deleting the row.
    product.is_active = False
    db.session.commit()

    return jsonify({"message": "Product deactivated."})
