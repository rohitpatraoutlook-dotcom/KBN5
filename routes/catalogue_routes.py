from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, url_for
from sqlalchemy import or_

from extensions import db
from models import Product
from services.auth_service import api_admin_required

catalogue_bp = Blueprint(
    "catalogue",
    __name__,
    url_prefix="/api/v1",
)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


def product_json(product):
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "description": product.description or "",
        "price_paise": product.price_paise,
        "stock_quantity": product.stock_quantity,
        "category_id": product.category_id,
        "category_name": getattr(product, "category_name", None),
        "image_key": product.image_key,
        "in_stock": product.stock_quantity > 0,
    }


@catalogue_bp.get("/catalogue/search")
def search_catalogue():
    query = request.args.get("q", "").strip()
    category_id = request.args.get("category_id", type=int)
    stock_only = request.args.get("in_stock", "false").lower() in {
        "1", "true", "yes"
    }
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 20, type=int), 1), 100)

    products = Product.query.filter_by(is_active=True)

    if query:
        pattern = f"%{query}%"
        products = products.filter(
            or_(
                Product.name.ilike(pattern),
                Product.description.ilike(pattern),
                Product.slug.ilike(pattern),
            )
        )

    if category_id is not None:
        products = products.filter(Product.category_id == category_id)

    if stock_only:
        products = products.filter(Product.stock_quantity > 0)

    pagination = products.order_by(Product.name.asc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )

    return jsonify({
        "items": [product_json(p) for p in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
    })


@catalogue_bp.post("/admin/products/<int:product_id>/upload-image")
@api_admin_required
def upload_product_image(product_id):
    product = db.session.get(Product, product_id)
    if product is None:
        return jsonify({"error": "Product not found."}), 404

    uploaded = request.files.get("image")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Select an image file."}), 400

    original_name = Path(uploaded.filename).name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": "Allowed image formats: JPG, JPEG, PNG and WEBP."
        }), 400

    uploaded.stream.seek(0, 2)
    size = uploaded.stream.tell()
    uploaded.stream.seek(0)

    if size <= 0 or size > MAX_UPLOAD_BYTES:
        return jsonify({"error": "Image must be between 1 byte and 5 MB."}), 400

    upload_folder = Path(
        current_app.config.get(
            "KBN5_UPLOAD_FOLDER",
            str(Path(current_app.instance_path) / "product_images"),
        )
    )
    upload_folder.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid4().hex}{extension}"
    destination = upload_folder / filename
    uploaded.save(destination)

    # Store the generated filename, not a user-controlled path.
    product.image_key = filename
    db.session.commit()

    return jsonify({
        "message": "Product image uploaded.",
        "product_id": product.id,
        "image_key": filename,
        "image_url": url_for(
            "catalogue.product_image",
            filename=filename,
            _external=True,
        ),
    }), 201


@catalogue_bp.get("/catalogue/images/<path:filename>")
def product_image(filename):
    from flask import send_from_directory

    # Never allow path traversal or nested filenames.
    if Path(filename).name != filename:
        return jsonify({"error": "Invalid image filename."}), 400

    folder = current_app.config.get(
        "KBN5_UPLOAD_FOLDER",
        str(Path(current_app.instance_path) / "product_images"),
    )
    return send_from_directory(folder, filename)
