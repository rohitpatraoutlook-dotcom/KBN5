import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def load_local_env():
    env_file = BASE_DIR / ".env"

    if not env_file.is_file():
        return

    for line in env_file.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(key, value)


load_local_env()


def is_render_environment():
    return (
        os.getenv("RENDER", "").lower() == "true"
        or bool(os.getenv("RENDER_SERVICE_ID"))
    )


def get_database_url():
    url = os.getenv("DATABASE_URL", "").strip()

    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    if is_render_environment():
        raise RuntimeError(
            "DATABASE_URL is required on Render. "
            "Configure the PostgreSQL connection before deployment."
        )

    return f"sqlite:///{BASE_DIR / 'instance' / 'kbn5.db'}"


def get_secret_key():
    secret = os.getenv("SECRET_KEY", "").strip()

    if secret:
        return secret

    if is_render_environment():
        raise RuntimeError(
            "SECRET_KEY is required on Render. "
            "Set a long, random secret in the service environment."
        )

    return "development-only-change-me"


class Config:
    SECRET_KEY = get_secret_key()
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )

    PERMANENT_SESSION_LIFETIME = 43200

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
