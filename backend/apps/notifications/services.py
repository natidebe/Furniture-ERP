"""notify(): who hears about what (BUILD_PHASES.md 4.1).

Rows are written in the caller's transaction, so a change that rolls back never notifies.
Only people with a linked Telegram account get rows; everyone else sees the same items in
the web app's lists.
"""

import logging

from django.contrib.auth import get_user_model
from django.utils import timezone

from . import templates
from .models import AlertLog, NotificationOutbox

logger = logging.getLogger(__name__)


def _active_linked():
    return get_user_model().objects.filter(is_active=True, telegram_id__isnull=False)


def _at(location_id):
    return _active_linked().filter(home_location_id=location_id)


def _with_permission(permission: str, roles=("accountant",)):
    users = _active_linked().filter(role__in=roles)
    return [u for u in users if u.has_erp_permission(permission)]


def _admins():
    return _active_linked().filter(role="admin")


def _recipients_and_message(event_type: str, obj, context: dict):
    """(users, message) for an event; users may be a list or queryset."""
    if event_type == "stock_request.created":
        return (_at(obj.source_location_id).filter(role="storekeeper"),
                templates.stock_request_card(obj))
    if event_type == "stock_request.acknowledged":
        return [obj.salesperson], templates.stock_request_update(obj, "was acknowledged at "
                                                                 f"{obj.source_location.code}")
    if event_type == "stock_request.released":
        return [obj.salesperson], templates.stock_request_update(obj, "was released",
                                                                 context.get("release"))
    if event_type == "stock_request.rejected":
        return [obj.salesperson], templates.stock_request_update(obj, "was rejected")
    if event_type == "stock_request.cancelled":
        return (_at(obj.source_location_id).filter(role="storekeeper"),
                templates.stock_request_update(obj, "was cancelled"))
    if event_type == "transfer.sent":
        return _at(obj.to_location_id), templates.transfer_sent(obj)
    if event_type == "transfer.discrepancy":
        return (_with_permission("approve_adjustments"),
                templates.transfer_discrepancy(obj))
    if event_type == "payment.to_verify":
        return _with_permission("verify_payments"), templates.payment_to_verify(obj)
    if event_type == "payment.rejected":
        return [obj.recorded_by], templates.payment_rejected(obj)
    if event_type == "adjustment.proposed":
        return ([u for u in _with_permission("approve_adjustments")
                 if u.pk != obj.proposed_by_id],
                templates.adjustment_proposed(obj))
    if event_type == "order.goods_arrived":
        return [obj.salesperson], templates.order_update(
            obj, f"— goods arrived at {obj.branch.code}; hand them over when the customer "
                 f"comes.")
    if event_type == "order.prepared":
        return [obj.salesperson], templates.order_update(obj, "is prepared at the warehouse.")
    if event_type == "order.released":
        return [obj.salesperson], templates.order_update(obj, "— all goods handed over.")
    if event_type == "order.cancelled":
        return [obj.salesperson], templates.order_update(obj, "was cancelled.")
    if event_type == "stock.low":
        storekeepers = _active_linked().filter(role="storekeeper",
                                               home_location__can_release=True)
        return (list(_admins()) + list(storekeepers),
                templates.low_stock(obj, context["total_new"]))
    if event_type == "stock.mismatch":
        return _admins(), templates.stock_mismatch(context["count"])
    if event_type.startswith("report."):
        return _admins(), context["message"]
    return [], None


def notify(event_type: str, obj, **context) -> int:
    """Queue `event_type` about `obj` for the right people. Returns how many rows it wrote.
    Call it inside the business transaction."""
    users, message = _recipients_and_message(event_type, obj, context)
    if message is None:
        logger.debug("No recipients defined for %s", event_type)
        return 0
    seen, rows = set(), []
    for user in users:
        if (user is None or user.pk in seen or not user.is_active
                or not user.telegram_id):
            continue
        seen.add(user.pk)
        rows.append(NotificationOutbox(event_type=event_type, target_user=user,
                                       chat_id=user.telegram_id, payload=message))
    NotificationOutbox.objects.bulk_create(rows)
    return len(rows)


def once_today(key: str) -> bool:
    """True the first time `key` is seen today (Addis Ababa), False afterwards."""
    _, created = AlertLog.objects.get_or_create(key=key, day=timezone.localdate())
    return created
