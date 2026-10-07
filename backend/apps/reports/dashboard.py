"""GET /dashboard/ — the home page (P-02) for the signed-in user's role in one call.

Every block is {"count": total, "items": [the first DASHBOARD_ITEMS]}, so a tile shows the
count and links to its filtered list for the rest. Scope and Personal-amount visibility follow
the same rules as the lists and reports the tiles link to.
"""

from datetime import timedelta

from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from apps.customers.selectors import customers_with_balance
from apps.inventory.models import AdjustmentStatus, StockAdjustment, StockTransfer, TransferStatus
from apps.inventory.selectors import low_stock_products, movements_for_user
from apps.requests.models import OPEN_STATUSES, RequestStatus
from apps.requests.selectors import requests_for_user
from apps.sales.models import BILLABLE_STATUSES, OrderPaymentStatus, SalesOrderLine
from apps.sales.selectors import orders_for_user

from .selectors import _ec, _money, sales_report, unverified_payments_report

DASHBOARD_ITEMS = 10
SHORTAGE_DAYS = 30  # transfers received short in the last 30 days


def _block(qs, row) -> dict:
    return {"count": qs.count(), "items": [row(obj) for obj in qs[:DASHBOARD_ITEMS]]}


def _request_row(r) -> dict:
    return {"id": r.pk, "number": r.number, "status": r.status,
            "branch": r.requesting_location.code, "source": r.source_location.code,
            "customer": r.customer.name if r.customer else None,
            "salesperson": r.salesperson.full_name, "created_at": r.created_at,
            "date_ec": _ec(r.created_at),
            "lines": ", ".join(f"{ln.qty_requested} × {ln.product.code}"
                               for ln in r.lines.all())}


def _open_requests(user):
    # The storekeeper's queue: Pending first, then Acknowledged / Partially released;
    # newest first within each.
    return (requests_for_user(user).filter(status__in=OPEN_STATUSES)
            .prefetch_related("lines__product")
            .annotate(pending_first=Case(When(status=RequestStatus.PENDING, then=Value(0)),
                                         default=Value(1), output_field=IntegerField()))
            .order_by("pending_first", "-created_at"))


def _transfer_row(t) -> dict:
    return {"id": t.pk, "number": t.number, "from": t.from_location.code,
            "to": t.to_location.code, "status": t.status, "sent_at": t.sent_at,
            "date_ec": _ec(t.sent_at), "transaction": t.transaction_number,
            "short": t.has_discrepancy}


def _transfers(**filters):
    return (StockTransfer.objects.filter(**filters)
            .select_related("from_location", "to_location"))


def _order_row(o) -> dict:
    return {"id": o.pk, "number": o.number, "customer": o.customer.name,
            "branch": o.branch.code, "salesperson": o.salesperson.full_name,
            "total": _money(o.total_amount), "payment_status": o.payment_status,
            "fulfillment_status": o.fulfillment_status, "confirmed_at": o.confirmed_at,
            "date_ec": _ec(o.confirmed_at) if o.confirmed_at else ""}


def _low_stock() -> dict:
    qs = low_stock_products().filter(is_active=True).order_by("code")
    return _block(qs, lambda p: {"id": p.pk, "code": p.code, "name": p.name,
                                 "sellable": p.total_new, "min_stock": p.min_stock,
                                 "shortfall": p.min_stock - p.total_new})


def _today_sales(user, *, by_branch: bool = False) -> dict:
    today = timezone.localdate()
    report = sales_report(user, today, today)
    keys = ["period_label", "sales", "returns", "net_sales", "transactions", "paid", "credit",
            "received"]
    if by_branch:
        keys += ["by_branch", "by_salesperson"]
    return {k: report[k] for k in keys}


def salesperson_dashboard(user) -> dict:
    branch = user.home_location_id
    own_billable = orders_for_user(user).filter(fulfillment_status__in=BILLABLE_STATUSES)
    held = (SalesOrderLine.objects.filter(order__in=own_billable, qty_awaiting__gt=0)
            .select_related("order__customer", "product").order_by("order__confirmed_at"))
    return {
        "sales_today": _today_sales(user),
        "waiting_for_payment": _block(
            own_billable.exclude(payment_status=OrderPaymentStatus.PAID)
            .order_by("confirmed_at"), _order_row),
        "open_requests": _block(_open_requests(user), _request_row),
        "transfers_arriving": _block(
            _transfers(status=TransferStatus.IN_TRANSIT, to_location=branch)
            if branch else StockTransfer.objects.none(), _transfer_row),
        "held_for_customers": _block(held, lambda ln: {
            "order_id": ln.order_id, "order": ln.order.number,
            "customer": ln.order.customer.name, "product": ln.product.code,
            "qty": ln.qty_awaiting}),
    }


def storekeeper_dashboard(user) -> dict:
    location = user.home_location_id
    movements = movements_for_user(user).order_by("-occurred_at", "-id")
    return {
        "request_queue": _block(_open_requests(user), _request_row),
        "low_stock": _low_stock(),
        "recent_movements": _block(movements, lambda m: {
            "id": m.pk, "number": m.number, "type": m.type, "condition": m.condition,
            "product": m.product.code, "qty": m.qty,
            "from": m.from_location.code if m.from_location else None,
            "to": m.to_location.code if m.to_location else None,
            "occurred_at": m.occurred_at, "date_ec": _ec(m.occurred_at),
            "transaction": m.transaction_number}),
        "transfers_not_received": _block(
            _transfers(status=TransferStatus.IN_TRANSIT, from_location=location)
            if location else StockTransfer.objects.none(), _transfer_row),
    }


def accountant_dashboard(user, *, admin: bool = False) -> dict:
    to_verify = unverified_payments_report(user)
    shortages = _transfers(status=TransferStatus.RECEIVED,
                           received_at__gte=timezone.now() - timedelta(days=SHORTAGE_DAYS)
                           ).exclude(discrepancy_note="").order_by("-received_at")
    adjustments = (StockAdjustment.objects.filter(status=AdjustmentStatus.PROPOSED)
                   .select_related("location", "product", "proposed_by")
                   .order_by("proposed_at"))
    over_limit = customers_with_balance().filter(over_limit=True).order_by("-outstanding")
    data = {
        "payments_to_verify": {"count": to_verify["count"], "total": to_verify["total"],
                               "items": to_verify["payments"][:DASHBOARD_ITEMS]},
        "today": _today_sales(user, by_branch=admin),
        "adjustments_to_approve": _block(adjustments, lambda a: {
            "id": a.pk, "number": a.number, "location": a.location.code,
            "product": a.product.code, "qty_delta": a.qty_delta, "condition": a.condition,
            "reason": a.reason, "proposed_by": a.proposed_by.full_name,
            "proposed_by_id": a.proposed_by_id, "date_ec": _ec(a.proposed_at)}),
        "transfers_with_shortages": _block(shortages, lambda t: {
            **_transfer_row(t), "received_at": t.received_at,
            "discrepancy_note": t.discrepancy_note}),
        "customers_over_limit": _block(over_limit, lambda c: {
            "id": c.pk, "name": c.name, "shop_name": c.shop_name, "phone": c.phone,
            "credit_allowed": c.credit_allowed,
            "credit_limit": _money(c.credit_limit) if c.credit_limit is not None else None,
            "outstanding": _money(c.outstanding)}),
    }
    if admin:
        data["low_stock"] = _low_stock()
    return data


def dashboard(user) -> dict:
    builders = {
        "salesperson": salesperson_dashboard,
        "storekeeper": storekeeper_dashboard,
        "accountant": accountant_dashboard,
        "admin": lambda u: accountant_dashboard(u, admin=True),
    }
    build = builders.get(user.role)
    return {"role": user.role, **(build(user) if build else {})}
