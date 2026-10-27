import re

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Category
from services.auth_service import api_admin_required

admin_category_bp = Blueprint(
    "admin_categories",
    __name__,
    url_prefix="/api/v1/admin/categories",
)


def make_slug(value):
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:120].strip("-")


@admin_category_bp.get("/")
@api_admin_required
def list_categories():
    categories = Category.query.order_by(Category.name.asc()).all()

    return jsonify({
        "items": [
            {
                "id": category.id,
                "name": category.name,
                "slug": category.slug,
                "is_active": category.is_active,
            }
            for category in categories
        ]
    })


@admin_category_bp.post("/")
@api_admin_required
def create_category():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()

    if not name or len(name) > 100:
        return jsonify({"error": "Category name is required (max 100 characters)."}), 400

    if Category.query.filter_by(name=name).first():
        return jsonify({"error": "Category already exists."}), 409

    base_slug = make_slug(name)
    if not base_slug:
        return jsonify({"error": "Category name must contain letters or numbers."}), 400

    slug = base_slug
    suffix = 2

    while Category.query.filter_by(slug=slug).first():
        slug = f"{base_slug[:110]}-{suffix}"
        suffix += 1

    category = Category(name=name, slug=slug, is_active=True)

    try:
        db.session.add(category)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not save category."}), 409

    return jsonify({
        "category": {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "is_active": category.is_active,
        }
    }), 201


@admin_category_bp.patch("/<int:category_id>")
@api_admin_required
def update_category(category_id):
    category = db.session.get(Category, category_id)

    if category is None:
        return jsonify({"error": "Category not found."}), 404

    data = request.get_json(silent=True) or {}

    if "name" in data:
        name = str(data["name"]).strip()

        if not name or len(name) > 100:
            return jsonify({"error": "Invalid category name."}), 400

        duplicate = Category.query.filter(
            Category.name == name,
            Category.id != category.id,
        ).first()

        if duplicate:
            return jsonify({"error": "Category name already exists."}), 409

        category.name = name

    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return jsonify({"error": "is_active must be true or false."}), 400
        category.is_active = data["is_active"]

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not update category."}), 409

    return jsonify({
        "category": {
            "id": category.id,
            "name": category.name,
            "slug": category.slug,
            "is_active": category.is_active,
        }
    })
