from datetime import datetime, timedelta, timezone

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from flask import current_app


TOKEN_SALT = "kbn5-api-access-v1"
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 12


def _serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"],
        salt=TOKEN_SALT,
    )


def create_access_token(user_id):
    return _serializer().dumps({
        "sub": int(user_id),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    })


def verify_access_token(token):
    try:
        payload = _serializer().loads(
            token,
            max_age=TOKEN_MAX_AGE_SECONDS,
        )

        user_id = payload.get("sub")

        if not isinstance(user_id, int) or user_id <= 0:
            return None

        return user_id

    except (BadSignature, SignatureExpired, TypeError, ValueError, AttributeError):
        return None
