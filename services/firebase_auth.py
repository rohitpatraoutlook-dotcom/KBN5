import requests
from functools import wraps

from flask import current_app, g, jsonify, request


def verify_firebase_token(token):
    api_key = current_app.config.get("FIREBASE_WEB_API_KEY")

    if not api_key:
        raise RuntimeError("Firebase Web API key is not configured")

    url = (
        "https://identitytoolkit.googleapis.com/v1/"
        f"accounts:lookup?key={api_key}"
    )

    response = requests.post(
        url,
        json={"idToken": token},
        timeout=10,
    )
    response.raise_for_status()

    users = response.json().get("users", [])

    if not users:
        raise ValueError("Firebase token is invalid")

    user = users[0]

    return {
        "uid": user["localId"],
        "email": user.get("email"),
        "email_verified": user.get("emailVerified", False),
        "display_name": user.get("displayName"),
    }


def firebase_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        scheme, _, token = header.partition(" ")

        if scheme.lower() != "bearer" or not token.strip():
            return jsonify({"error": "missing_bearer_token"}), 401

        try:
            g.firebase_claims = verify_firebase_token(token.strip())
        except requests.RequestException:
            current_app.logger.warning("Firebase verification service unavailable")
            return jsonify({"error": "authentication_service_unavailable"}), 503
        except (ValueError, KeyError):
            return jsonify({"error": "invalid_or_expired_token"}), 401
        except RuntimeError:
            return jsonify({"error": "authentication_not_configured"}), 503

        return view(*args, **kwargs)

    return wrapped
