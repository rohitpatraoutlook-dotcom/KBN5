from extensions import db
from models import Notification, NotificationPreference

STATUS_MESSAGES = {
    "confirmed": (
        "Order confirmed",
        "Your order has been confirmed.",
    ),
    "stock_reserved": (
        "Items reserved",
        "Items for your order have been reserved.",
    ),
    "picking_assigned": (
        "Order preparation assigned",
        "Your order has been assigned for preparation.",
    ),
    "picking": (
        "Preparing your order",
        "Your items are being collected.",
    ),
    "picked": (
        "Items collected",
        "Your items have been collected.",
    ),
    "packing": (
        "Packing your order",
        "Your order is being packed.",
    ),
    "ready_for_dispatch": (
        "Order ready",
        "Your order is ready for dispatch.",
    ),
    "delivery_assigned": (
        "Delivery assigned",
        "A delivery assignment has been created for your order.",
    ),
    "picked_up": (
        "Order picked up",
        "Your order has been picked up for delivery.",
    ),
    "out_for_delivery": (
        "Out for delivery",
        "Your order is on its way.",
    ),
    "delivered": (
        "Order delivered",
        "Your order has been marked as delivered.",
    ),
    "cancelled": (
        "Order cancelled",
        "Your order has been cancelled.",
    ),
}


def notifications_enabled(user_id, notification_type):
    """Missing preferences mean notifications remain enabled by default."""
    preference = NotificationPreference.query.filter_by(
        user_id=user_id
    ).first()

    if preference is None:
        return True

    if notification_type == "order_update":
        return preference.order_updates_enabled

    if notification_type == "general":
        return preference.general_notifications_enabled

    return True


def create_notification(
    user_id,
    title,
    message,
    notification_type="general",
    related_order_id=None,
):
    """Add a notification to the current database transaction."""
    if not notifications_enabled(user_id, notification_type):
        return None

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_order_id=related_order_id,
    )

    db.session.add(notification)
    return notification


def create_order_status_notification(order):
    """Create an order update only when the customer allows it."""
    details = STATUS_MESSAGES.get(order.status)

    if details is None:
        return None

    title, message = details

    return create_notification(
        user_id=order.user_id,
        title=title,
        message=f"{message} Order: {order.order_number}",
        notification_type="order_update",
        related_order_id=order.id,
    )
