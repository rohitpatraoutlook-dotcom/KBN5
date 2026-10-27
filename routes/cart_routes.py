from flask import Blueprint, g, jsonify, request

from extensions import db
from models import CartItem, Product
from services.auth_service import api_login_required

cart_bp = Blueprint("cart", __name__, url_prefix="/api/v1/cart")


def cart_payload(user_id):
    items = (
        CartItem.query
        .filter_by(user_id=user_id)
        .order_by(CartItem.id.asc())
        .all()
    )

    result = []
    total_paise = 0

    for item in items:
        product = item.product

        if product is None or not product.is_active:
            continue

        subtotal = product.price_paise * item.quantity
        total_paise += subtotal

        result.append({
            "id": item.id,
            "product_id": product.id,
            "name": product.name,
            "unit_price_paise": product.price_paise,
            "quantity": item.quantity,
            "subtotal_paise": subtotal,
            "stock_quantity": product.stock_quantity,
            "image_key": product.image_key,
        })

    return {
        "items": result,
        "total_paise": total_paise,
        "item_count": sum(item["quantity"] for item in result),
    }


@cart_bp.get("/")
@api_login_required
def get_cart():
    return jsonify(cart_payload(g.kbn5_user.id))


@cart_bp.post("/items")
@api_login_required
def add_item():
    data = request.get_json(silent=True) or {}

    product_id = data.get("product_id")
    quantity = data.get("quantity", 1)

    if not isinstance(product_id, int) or isinstance(product_id, bool):
        return jsonify({"error": "product_id must be an integer."}), 400

    if not isinstance(quantity, int) or isinstance(quantity, bool):
        return jsonify({"error": "quantity must be an integer."}), 400

    if quantity < 1 or quantity > 50:
        return jsonify({"error": "Quantity must be between 1 and 50."}), 400

    product = db.session.get(Product, product_id)

    if product is None or not product.is_active:
        return jsonify({"error": "Product not found."}), 404

    if product.stock_quantity < 1:
        return jsonify({"error": "Product is out of stock."}), 409

    user_id = g.kbn5_user.id
    item = CartItem.query.filter_by(
        user_id=user_id,
        product_id=product.id,
    ).first()

    new_quantity = quantity + (item.quantity if item else 0)

    if new_quantity > 50:
        return jsonify({"error": "Maximum quantity per product is 50."}), 400

    if new_quantity > product.stock_quantity:
        return jsonify({"error": "Requested quantity exceeds available stock."}), 409

    if item:
        item.quantity = new_quantity
    else:
        item = CartItem(
            user_id=user_id,
            product_id=product.id,
            quantity=quantity,
        )
        db.session.add(item)

    db.session.commit()

    return jsonify({
        "message": "Cart updated.",
        **cart_payload(user_id),
    }), 200


@cart_bp.patch("/items/<int:item_id>")
@api_login_required
def update_item(item_id):
    data = request.get_json(silent=True) or {}
    quantity = data.get("quantity")

    if not isinstance(quantity, int) or isinstance(quantity, bool):
        return jsonify({"error": "quantity must be an integer."}), 400

    if quantity < 1 or quantity > 50:
        return jsonify({"error": "Quantity must be between 1 and 50."}), 400

    item = CartItem.query.filter_by(
        id=item_id,
        user_id=g.kbn5_user.id,
    ).first()

    if item is None:
        return jsonify({"error": "Cart item not found."}), 404

    if item.product is None or not item.product.is_active:
        return jsonify({"error": "Product is unavailable."}), 409

    if quantity > item.product.stock_quantity:
        return jsonify({"error": "Requested quantity exceeds available stock."}), 409

    item.quantity = quantity
    db.session.commit()

    return jsonify({
        "message": "Quantity updated.",
        **cart_payload(g.kbn5_user.id),
    })


@cart_bp.delete("/items/<int:item_id>")
@api_login_required
def remove_item(item_id):
    item = CartItem.query.filter_by(
        id=item_id,
        user_id=g.kbn5_user.id,
    ).first()

    if item is None:
        return jsonify({"error": "Cart item not found."}), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify({
        "message": "Item removed.",
        **cart_payload(g.kbn5_user.id),
    })
