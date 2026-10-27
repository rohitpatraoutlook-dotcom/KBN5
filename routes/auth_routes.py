import re

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_user, logout_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import User
from services.token_service import create_access_token
from services.auth_service import api_login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


def json_error(message, status=400):
    return jsonify({"error": message}), status


def user_payload(user):
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
    }


def auth_response(user, message, status=200):
    return jsonify({
        "message": message,
        "user": user_payload(user),
        "access_token": create_access_token(user.id),
        "token_type": "Bearer",
        "expires_in": 43200,
    }), status


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip().lower()
    email = str(data.get("email", "")).strip().lower()
    password = data.get("password", "")
    display_name = str(data.get("display_name", username)).strip()

    if not isinstance(password, str):
        return json_error("Password must be a string.")

    if not re.fullmatch(r"[a-z0-9_]{3,40}", username):
        return json_error(
            "Username must be 3-40 lowercase letters, numbers or underscores."
        )

    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        return json_error("Enter a valid email address.")

    if not 12 <= len(password) <= 128:
        return json_error("Password must be 12-128 characters.")

    if not display_name or len(display_name) > 120:
        return json_error("Display name must be 1-120 characters.")

    existing = User.query.filter(
        or_(User.username == username, User.email == email)
    ).first()

    if existing:
        return json_error("Username or email is already registered.", 409)

    user = User(
        username=username,
        email=email,
        display_name=display_name,
        role="customer",
    )
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return json_error("Username or email is already registered.", 409)

    login_user(user, fresh=True)
    return auth_response(user, "Registration successful.", 201)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}

    identity = str(data.get("identity", "")).strip().lower()
    password = data.get("password", "")

    if not identity or not isinstance(password, str):
        return json_error("Username/email and password are required.")

    user = User.query.filter(
        or_(User.username == identity, User.email == identity)
    ).first()

    if user is None or not user.is_active or not user.check_password(password):
        return json_error("Invalid credentials.", 401)

    login_user(user, fresh=True)
    return auth_response(user, "Login successful.")


@auth_bp.post("/logout")
@api_login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully."})


@auth_bp.get("/me")
@api_login_required
def me():
    from flask import g
    return jsonify({"user": user_payload(g.kbn5_user)})
