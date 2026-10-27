import re

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ServiceableArea
from services.auth_service import api_admin_required

admin_area_bp = Blueprint(
    "admin_areas",
    __name__,
    url_prefix="/api/v1/admin/serviceable-areas",
)


def area_payload(area):
    return {
        "id": area.id,
        "area_name": area.area_name,
        "pincode": area.pincode,
        "is_active": area.is_active,
        "delivery_fee_paise": area.delivery_fee_paise,
        "minimum_order_paise": area.minimum_order_paise,
    }


def validate_area(data, partial=False):
    result = {}

    if not partial or "area_name" in data:
        name = data.get("area_name")
        if not isinstance(name, str) or not name.strip():
            return None, "Area name is required."
        if len(name.strip()) > 120:
            return None, "Area name must be 120 characters or fewer."
        result["area_name"] = name.strip()

    if not partial or "pincode" in data:
        pincode = data.get("pincode")
        if not isinstance(pincode, str) or not re.fullmatch(r"[0-9]{6}", pincode):
            return None, "PIN code must contain exactly 6 digits."
        result["pincode"] = pincode

    for field in ("delivery_fee_paise", "minimum_order_paise"):
        if not partial or field in data:
            value = data.get(field, 0)
            if type(value) is not int or value < 0 or value > 100_000_000:
                return None, f"{field} must be a non-negative integer in paise."
            result[field] = value

    if "is_active" in data:
        if type(data["is_active"]) is not bool:
            return None, "is_active must be true or false."
        result["is_active"] = data["is_active"]

    return result, None


@admin_area_bp.get("/")
@api_admin_required
def list_areas():
    areas = ServiceableArea.query.order_by(
        ServiceableArea.area_name.asc()
    ).all()

    return jsonify({
        "items": [area_payload(area) for area in areas]
    })


@admin_area_bp.post("/")
@api_admin_required
def create_area():
    data = request.get_json(silent=True) or {}
    cleaned, error = validate_area(data)

    if error:
        return jsonify({"error": error}), 400

    area = ServiceableArea(**cleaned)

    try:
        db.session.add(area)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "This PIN code is already configured."
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not create serviceable area."}), 500

    return jsonify({
        "message": "Serviceable area created.",
        "area": area_payload(area),
    }), 201


@admin_area_bp.patch("/<int:area_id>")
@api_admin_required
def update_area(area_id):
    area = db.session.get(ServiceableArea, area_id)

    if area is None:
        return jsonify({"error": "Serviceable area not found."}), 404

    data = request.get_json(silent=True) or {}
    cleaned, error = validate_area(data, partial=True)

    if error:
        return jsonify({"error": error}), 400

    for key, value in cleaned.items():
        setattr(area, key, value)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({
            "error": "That PIN code is already configured."
        }), 409
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update serviceable area."}), 500

    return jsonify({
        "message": "Serviceable area updated.",
        "area": area_payload(area),
    })


@admin_area_bp.delete("/<int:area_id>")
@api_admin_required
def deactivate_area(area_id):
    area = db.session.get(ServiceableArea, area_id)

    if area is None:
        return jsonify({"error": "Serviceable area not found."}), 404

    # Keep the record for history; disable future serviceability instead.
    area.is_active = False

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not deactivate serviceable area."}), 500

    return jsonify({"message": "Serviceable area deactivated."})
