from datetime import datetime, timezone

from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


def utc_now():
    return datetime.now(timezone.utc)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False, index=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="customer")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method="scrypt")

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(120), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, index=True)
    slug = db.Column(db.String(180), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    price_paise = db.Column(db.Integer, nullable=False, default=0)
    stock_quantity = db.Column(db.Integer, nullable=False, default=0)
    image_key = db.Column(db.String(255), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    category = db.relationship("Category", backref="products")


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(40), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="placed")
    payment_status = db.Column(db.String(30), nullable=False, default="pending")
    total_paise = db.Column(db.Integer, nullable=False, default=0)
    delivery_fee_paise = db.Column(db.Integer, nullable=False, default=0)
    delivery_address = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)

    user = db.relationship("User", backref="orders")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
        index=True,
    )

    # Product price at the moment of checkout.
    unit_price_paise = db.Column(db.Integer, nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    # Preserve the product name even if the catalogue changes later.
    product_name = db.Column(db.String(160), nullable=False)

    order = db.relationship(
        "Order",
        backref=db.backref("items", lazy=True),
    )

    product = db.relationship("Product")


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    product_id = db.Column(
        db.Integer,
        db.ForeignKey("products.id"),
        nullable=False,
        index=True,
    )

    quantity = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    user = db.relationship(
        "User",
        backref=db.backref("cart_items", lazy=True),
    )

    product = db.relationship("Product")

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_cart_user_product",
        ),
    )


class ServiceableArea(db.Model):
    __tablename__ = "serviceable_areas"

    id = db.Column(db.Integer, primary_key=True)
    area_name = db.Column(db.String(120), nullable=False)
    pincode = db.Column(db.String(10), unique=True, nullable=False, index=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    delivery_fee_paise = db.Column(db.Integer, nullable=False, default=0)
    minimum_order_paise = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )


class CustomerAddress(db.Model):
    __tablename__ = "customer_addresses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    label = db.Column(db.String(40), nullable=False, default="Home")
    recipient_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    address_line = db.Column(db.String(300), nullable=False)
    landmark = db.Column(db.String(160), nullable=True)
    area_name = db.Column(db.String(120), nullable=False)
    pincode = db.Column(db.String(10), nullable=False, index=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    user = db.relationship(
        "User",
        backref=db.backref("saved_addresses", lazy=True),
    )




class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    method = db.Column(db.String(30), nullable=False, default="cod")
    status = db.Column(db.String(30), nullable=False, default="pending")
    amount_paise = db.Column(db.Integer, nullable=False)
    provider_reference = db.Column(db.String(160), nullable=True, unique=True)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    order = db.relationship(
        "Order",
        backref=db.backref("payment", uselist=False),
    )


class OrderStatusHistory(db.Model):
    __tablename__ = "order_status_history"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=False,
        index=True,
    )

    status = db.Column(db.String(40), nullable=False)

    note = db.Column(db.String(250), nullable=True)

    changed_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    order = db.relationship(
        "Order",
        backref=db.backref(
            "status_history",
            lazy=True,
            order_by="OrderStatusHistory.created_at",
        ),
    )

    changed_by = db.relationship("User")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    notification_type = db.Column(
        db.String(40),
        nullable=False,
        default="general",
    )
    related_order_id = db.Column(
        db.Integer,
        db.ForeignKey("orders.id"),
        nullable=True,
        index=True,
    )
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    user = db.relationship(
        "User",
        backref=db.backref("notifications", lazy=True),
    )
    related_order = db.relationship("Order")


class NotificationPreference(db.Model):
    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    order_updates_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    general_notifications_enabled = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship(
        "User",
        backref=db.backref("notification_preference", uselist=False),
    )


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    action = db.Column(db.String(80), nullable=False, index=True)
    resource_type = db.Column(db.String(80), nullable=False)
    resource_id = db.Column(db.String(80), nullable=True)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )

    actor = db.relationship("User")
