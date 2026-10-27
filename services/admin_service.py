import getpass

from sqlalchemy import or_

from extensions import db
from models import User


def create_admin(username, email, display_name):
    username = username.strip().lower()
    email = email.strip().lower()
    display_name = display_name.strip()

    if not username or not email or not display_name:
        raise ValueError("Username, email and display name are required.")

    existing = User.query.filter(
        or_(User.username == username, User.email == email)
    ).first()

    if existing:
        raise ValueError("Username or email already exists.")

    password = getpass.getpass("Admin password (hidden): ")
    confirmation = getpass.getpass("Confirm admin password: ")

    if password != confirmation:
        raise ValueError("Passwords do not match.")

    if len(password) < 12 or len(password) > 128:
        raise ValueError("Password must be 12-128 characters.")

    admin = User(
        username=username,
        email=email,
        display_name=display_name,
        role="admin",
        is_active=True,
    )
    admin.set_password(password)

    db.session.add(admin)
    db.session.commit()

    return admin
