from pathlib import Path
from datetime import timedelta

from flask import Flask, g, jsonify, request
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text

from config import Config
from extensions import db, login_manager, migrate
from services.audit_service import record_admin_action

csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = None
    csrf.init_app(app)

    from models import User
    from routes.auth_routes import auth_bp
    from routes.cart_routes import cart_bp
    from routes.order_routes import order_bp
    from routes.payment_routes import payment_bp
    from routes.tracking_routes import tracking_bp
    from routes.profile_routes import profile_bp
    from routes.notification_routes import notification_bp
    from routes.notification_preference_routes import preference_bp
    from routes.customer_order_routes import customer_order_bp
    from routes.account_routes import account_bp
    from routes.admin_user_routes import admin_user_bp
    from routes.admin_audit_routes import admin_audit_bp
    from routes.product_routes import product_bp
    from routes.admin_product_routes import admin_product_bp
    from routes.admin_category_routes import admin_category_bp
    from routes.admin_order_routes import admin_order_bp
    from routes.admin_dashboard_routes import admin_dashboard_bp
    from routes.admin_image_routes import admin_image_bp
    from routes.address_routes import address_bp
    from routes.admin_area_routes import admin_area_bp

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (ValueError, TypeError):
            return None

    app.register_blueprint(auth_bp)
    app.register_blueprint(cart_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(payment_bp)
    app.register_blueprint(tracking_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(preference_bp)
    app.register_blueprint(customer_order_bp)
    app.register_blueprint(account_bp)
    app.register_blueprint(admin_user_bp)
    app.register_blueprint(admin_audit_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(admin_product_bp)
    app.register_blueprint(admin_category_bp)
    app.register_blueprint(admin_order_bp)
    app.register_blueprint(admin_dashboard_bp)
    app.register_blueprint(admin_image_bp)
    app.register_blueprint(address_bp)
    app.register_blueprint(admin_area_bp)

    @app.get("/")
    def index():
        return jsonify({
            "name": "KBN5 Core",
            "description": "5 Minutes in Kiriburu",
            "status": "prototype",
        })

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "kbn5-core"})

    @app.get("/health/database")
    def database_health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "connected"})
        except Exception:
            db.session.rollback()
            app.logger.exception("Database health check failed")
            return jsonify({
                "status": "error",
                "database": "unavailable",
            }), 503


    @app.after_request
    def audit_admin_mutation(response):
        if (
            request.path.startswith("/api/v1/admin/")
            and request.method in {"POST", "PATCH", "PUT", "DELETE"}
            and response.status_code < 400
        ):
            admin = getattr(g, "kbn5_user", None)

            if admin is not None and getattr(admin, "role", None) == "admin":
                # Account status changes already have explicit audit logging.
                if not request.path.startswith("/api/v1/admin/users/"):
                    parts = request.path.strip("/").split("/")
                    resource_type = parts[3] if len(parts) > 3 else "admin"
                    resource_id = next(
                        (part for part in reversed(parts) if part.isdigit()),
                        None,
                    )

                    try:
                        record_admin_action(
                            admin_id=admin.id,
                            action=f"admin_{request.method.lower()}_{resource_type}",
                            resource_type=resource_type,
                            resource_id=resource_id,
                            details={
                                "method": request.method,
                                "path": request.path,
                                "response_status": response.status_code,
                            },
                        )
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        app.logger.exception("Could not save admin audit log")

        return response

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)


@app.cli.command("init-db")
def init_db_command():
    """Create missing database tables without deleting existing tables."""
    with app.app_context():
        db.create_all()
        print("KBN5 database tables created where missing.")


@app.cli.command("create-admin")
def create_admin_command():
    """Create an administrator interactively."""
    import click
    from services.admin_service import create_admin

    username = click.prompt("Admin username")
    email = click.prompt("Admin email")
    display_name = click.prompt("Admin display name")

    try:
        with app.app_context():
            admin = create_admin(username, email, display_name)
            click.echo(f"Administrator created: {admin.username}")
    except ValueError as exc:
        click.echo(f"Could not create administrator: {exc}", err=True)
        raise SystemExit(1)
    except Exception:
        db.session.rollback()
        click.echo("Administrator creation failed.", err=True)
        raise SystemExit(1)
