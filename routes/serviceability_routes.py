from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import ServiceableArea
from services.auth_service import api_admin_required

serviceability_bp = Blueprint(
    "serviceability",
    __name__,
    url_prefix="/api/v1/serviceability",
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


@serviceability_bp.get("/")
def list_areas():
    areas = ServiceableArea.query.filter_by(
        is_active=True
    ).order_by(ServiceableArea.area_name.asc()).all()

    return jsonify({
        "items": [area_payload(area) for area in areas],
        "total": len(areas),
    })


@serviceability_bp.get("/check")
def check_pincode():
    pincode = request.args.get("pincode", "").strip()

    if not pincode.isdigit() or len(pincode) != 6:
        return jsonify({"error": "Enter a valid 6-digit Indian pincode."}), 400

    area = ServiceableArea.query.filter_by(
        pincode=pincode,
        is_active=True,
    ).first()

    if area is None:
        return jsonify({
            "serviceable": False,
            "pincode": pincode,
            "message": "Delivery is not available at this pincode yet.",
        })

    return jsonify({
        "serviceable": True,
        "message": "Delivery is available at this pincode.",
        "area": area_payload(area),
    })


@serviceability_bp.post("/admin")
@api_admin_required
def create_area():
    data = request.get_json(silent=True) or {}

    name = str(data.get("area_name", "")).strip()
    pincode = str(data.get("pincode", "")).strip()
    fee = data.get("delivery_fee_paise", 0)
    minimum = data.get("minimum_order_paise", 0)

    if not name or len(name) > 120:
        return jsonify({"error": "area_name is required (max 120 characters)."}), 400

    if not pincode.isdigit() or len(pincode) != 6:
        return jsonify({"error": "pincode must contain exactly 6 digits."}), 400

    for field, value in (
        ("delivery_fee_paise", fee),
        ("minimum_order_paise", minimum),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return jsonify({"error": f"{field} must be a non-negative integer."}), 400

    if ServiceableArea.query.filter_by(pincode=pincode).first():
        return jsonify({"error": "This pincode is already configured."}), 409

    area = ServiceableArea(
        area_name=name,
        pincode=pincode,
        is_active=True,
        delivery_fee_paise=fee,
        minimum_order_paise=minimum,
    )

    try:
        db.session.add(area)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not save serviceable area."}), 409

    return jsonify({
        "message": "Serviceable area created.",
        "area": area_payload(area),
    }), 201


@serviceability_bp.patch("/admin/<int:area_id>")
@api_admin_required
def update_area(area_id):
    area = db.session.get(ServiceableArea, area_id)
    if area is None:
        return jsonify({"error": "Serviceable area not found."}), 404

    data = request.get_json(silent=True) or {}

    if "area_name" in data:
        name = data["area_name"]
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
            return jsonify({"error": "Invalid area_name."}), 400
        area.area_name = name.strip()

    if "pincode" in data:
        pincode = str(data["pincode"]).strip()
        if not pincode.isdigit() or len(pincode) != 6:
            return jsonify({"error": "pincode must contain exactly 6 digits."}), 400

        existing = ServiceableArea.query.filter_by(pincode=pincode).first()
        if existing and existing.id != area.id:
            return jsonify({"error": "Pincode is already assigned to another area."}), 409

        area.pincode = pincode

    for field in ("delivery_fee_paise", "minimum_order_paise"):
        if field in data:
            value = data[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                return jsonify({"error": f"{field} must be a non-negative integer."}), 400
            setattr(area, field, value)

    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            return jsonify({"error": "is_active must be true or false."}), 400
        area.is_active = data["is_active"]

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Could not update serviceable area."}), 409

    return jsonify({
        "message": "Serviceable area updated.",
        "area": area_payload(area),
    })


@serviceability_bp.delete("/admin/<int:area_id>")
@api_admin_required
def deactivate_area(area_id):
    area = db.session.get(ServiceableArea, area_id)
    if area is None:
        return jsonify({"error": "Serviceable area not found."}), 404

    # Retain historical data; simply stop offering delivery.
    area.is_active = False
    db.session.commit()

    return jsonify({"message": "Serviceable area deactivated."})
