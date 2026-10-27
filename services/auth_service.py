from functools import wraps

from flask import g, jsonify, request
from flask_login import current_user

from extensions import db
from models import User
from services.token_service import verify_access_token


def api_error(message, status=401):
    return jsonify({"error": message}), status


def get_authenticated_user():
    # Prefer an explicit Bearer token for Flutter/API clients.
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if not token:
            return None

        user_id = verify_access_token(token)
        if user_id is None:
            return None

        user = db.session.get(User, user_id)
        if user is None or not user.is_active:
            return None

        return user

    # Otherwise allow the website's Flask-Login session.
    if current_user.is_authenticated and current_user.is_active:
        return current_user

    return None


def api_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_authenticated_user()

        if user is None:
            return api_error("Authentication required.", 401)

        g.kbn5_user = user
        return view(*args, **kwargs)

    return wrapped


def api_admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = get_authenticated_user()

        if user is None:
            return api_error("Authentication required.", 401)

        if user.role != "admin":
            return api_error("Administrator access required.", 403)

        g.kbn5_user = user
        return view(*args, **kwargs)

    return wrapped
