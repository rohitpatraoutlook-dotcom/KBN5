import re

from flask import Blueprint, g, jsonify, request
from sqlalchemy import select

from extensions import db
from models import CustomerAddress, ServiceableArea
from services.auth_service import api_login_required

address_bp = Blueprint(
    "addresses",
    __name__,
    url_prefix="/api/v1/addresses",
)


def address_payload(address):
    return {
        "id": address.id,
        "label": address.label,
        "recipient_name": address.recipient_name,
        "phone": address.phone,
        "address_line": address.address_line,
        "landmark": address.landmark,
        "area_name": address.area_name,
        "pincode": address.pincode,
        "is_default": address.is_default,
    }


def validate_address(data):
    required = [
        "recipient_name",
        "phone",
        "address_line",
        "area_name",
        "pincode",
    ]

    for field in required:
        if not isinstance(data.get(field), str) or not data[field].strip():
            return None, f"{field} is required."

    cleaned = {
        field: data[field].strip()
        for field in required
    }

    cleaned["label"] = str(data.get("label", "Home")).strip() or "Home"
    cleaned["landmark"] = str(data.get("landmark", "")).strip() or None

    if len(cleaned["recipient_name"]) > 120:
        return None, "Recipient name is too long."

    if not re.fullmatch(r"[0-9]{10}", cleaned["phone"]):
        return None, "Phone number must contain 10 digits."

    if len(cleaned["address_line"]) > 300:
        return None, "Address line is too long."

    if len(cleaned["area_name"]) > 120:
        return None, "Area name is too long."

    if len(cleaned["label"]) > 40:
        return None, "Address label is too long."

    if cleaned["landmark"] and len(cleaned["landmark"]) > 160:
        return None, "Landmark is too long."

    if not re.fullmatch(r"[0-9]{6}", cleaned["pincode"]):
        return None, "Enter a valid 6-digit PIN code."

    return cleaned, None


@address_bp.get("/")
@api_login_required
def list_addresses():
    addresses = CustomerAddress.query.filter_by(
        user_id=g.kbn5_user.id
    ).order_by(CustomerAddress.is_default.desc(), CustomerAddress.id.desc()).all()

    return jsonify({
        "items": [address_payload(item) for item in addresses]
    })


@address_bp.post("/")
@api_login_required
def create_address():
    data = request.get_json(silent=True) or {}
    cleaned, error = validate_address(data)

    if error:
        return jsonify({"error": error}), 400

    user_id = g.kbn5_user.id
    make_default = bool(data.get("is_default", False))

    try:
        with db.session.begin():
            existing = db.session.execute(
                select(CustomerAddress)
                .where(CustomerAddress.user_id == user_id)
            ).scalars().all()

            if len(existing) >= 20:
                return jsonify({
                    "error": "You can save up to 20 addresses."
                }), 409

            area = db.session.execute(
                select(ServiceableArea).where(
                    ServiceableArea.pincode == cleaned["pincode"],
                    ServiceableArea.is_active.is_(True),
                )
            ).scalar_one_or_none()

            if area is None:
                return jsonify({
                    "error": "Delivery is not available at this PIN code yet."
                }), 409

            if make_default or not existing:
                for old_address in existing:
                    old_address.is_default = False
                make_default = True

            address = CustomerAddress(
                user_id=user_id,
                **cleaned,
                is_default=make_default,
            )
            db.session.add(address)
            db.session.flush()

            result = address_payload(address)

    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not save address."}), 500

    return jsonify({
        "message": "Address saved.",
        "address": result,
    }), 201


@address_bp.patch("/<int:address_id>/default")
@api_login_required
def set_default_address(address_id):
    try:
        with db.session.begin():
            address = db.session.execute(
                select(CustomerAddress).where(
                    CustomerAddress.id == address_id,
                    CustomerAddress.user_id == g.kbn5_user.id,
                )
            ).scalar_one_or_none()

            if address is None:
                return jsonify({"error": "Address not found."}), 404

            addresses = db.session.execute(
                select(CustomerAddress).where(
                    CustomerAddress.user_id == g.kbn5_user.id
                )
            ).scalars().all()

            for item in addresses:
                item.is_default = item.id == address.id

            result = address_payload(address)

    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not update default address."}), 500

    return jsonify({
        "message": "Default address updated.",
        "address": result,
    })


@address_bp.delete("/<int:address_id>")
@api_login_required
def delete_address(address_id):
    try:
        with db.session.begin():
            address = db.session.execute(
                select(CustomerAddress).where(
                    CustomerAddress.id == address_id,
                    CustomerAddress.user_id == g.kbn5_user.id,
                )
            ).scalar_one_or_none()

            if address is None:
                return jsonify({"error": "Address not found."}), 404

            was_default = address.is_default
            user_id = g.kbn5_user.id
            db.session.delete(address)
            db.session.flush()

            if was_default:
                replacement = db.session.execute(
                    select(CustomerAddress)
                    .where(CustomerAddress.user_id == user_id)
                    .order_by(CustomerAddress.id.desc())
                    .limit(1)
                ).scalar_one_or_none()

                if replacement:
                    replacement.is_default = True

    except Exception:
        db.session.rollback()
        return jsonify({"error": "Could not delete address."}), 500

    return jsonify({"message": "Address deleted."})


@address_bp.get("/serviceability/<pincode>")
def check_serviceability(pincode):
    if not re.fullmatch(r"[0-9]{6}", pincode):
        return jsonify({"error": "Enter a valid 6-digit PIN code."}), 400

    area = ServiceableArea.query.filter_by(
        pincode=pincode,
        is_active=True,
    ).first()

    if area is None:
        return jsonify({
            "serviceable": False,
            "message": "KBN5 delivery is not available at this PIN code yet.",
        })

    return jsonify({
        "serviceable": True,
        "area_name": area.area_name,
        "pincode": area.pincode,
        "delivery_fee_paise": area.delivery_fee_paise,
        "minimum_order_paise": area.minimum_order_paise,
    })
