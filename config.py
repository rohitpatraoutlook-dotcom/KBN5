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


def get_database_url():
    url = os.getenv("DATABASE_URL", "").strip()

    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    return f"sqlite:///{BASE_DIR / 'instance' / 'kbn5.db'}"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-me")
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
