from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from models import Product

product_bp = Blueprint(
    "products",
    __name__,
    url_prefix="/api/v1/products",
)


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
        "category_name": product.category.name if product.category else "Essentials",
    }


@product_bp.get("/")
def list_products():
    query = Product.query.filter_by(is_active=True)

    search = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    if search:
        term = f"%{search[:100]}%"
        query = query.filter(
            or_(
                Product.name.ilike(term),
                Product.description.ilike(term),
            )
        )

    if category_id is not None:
        query = query.filter(Product.category_id == category_id)

    page = max(1, page)
    per_page = min(50, max(1, per_page))

    pagination = query.order_by(Product.name.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        "items": [product_payload(item) for item in pagination.items],
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


@product_bp.get("/<int:product_id>")
def get_product(product_id):
    product = Product.query.filter_by(
        id=product_id,
        is_active=True,
    ).first()

    if product is None:
        return jsonify({"error": "Product not found."}), 404

    return jsonify({"product": product_payload(product)})
