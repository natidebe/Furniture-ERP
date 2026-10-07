"""Reports (BUILD_PHASES.md 4.3). Definitions, agreed in the plan and fixed here:

- Period: a day, a week (Monday–Sunday), a month or a year, or any from–to range. Months
  and years are Ethiopian by default (Q12: Meskerem … Pagume; the year starts Meskerem 1);
  calendar="gregorian" gives January–December. All dates are Africa/Addis_Ababa.
- Sales: sales confirmed in the period (cancelled and voided excluded), at the value they were
  sold at (Σ line totals). Returns count in the period they happen, so a report run twice
  gives the same figures; net sales = sales − returns.
- Paid / unpaid: of the period's sales, how much is paid now (active allocations) and how much
  is still owed (credit).
- Money received: payments dated in the period that stand (unverified + verified), by
  Organization / Personal account.
- Credit collected: allocations made in the period to sales confirmed before it.
- Personal-account figures appear only for users with view_personal_payments.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.core import ethiopian
from apps.customers.models import Customer
from apps.customers.selectors import customer_balance
from apps.inventory.selectors import matrix_locations, products_with_total, stock_rows
from apps.payments.models import VALID_PAYMENT_STATUSES, Payment
from apps.payments.selectors import active_allocations
from apps.requests.models import OPEN_STATUSES
from apps.sales.models import BILLABLE_STATUSES, SalesOrder, SalesOrderLine, SalesReturn

ZERO = Decimal("0.00")
PERIODS = ("day", "week", "month", "year")
CALENDARS = ("ethiopian", "gregorian")


# ---------------------------------------------------------------- periods

def period_range(period: str = "day", anchor: date | None = None,
                 calendar: str = "ethiopian") -> tuple[date, date]:
    """(first day, last day) — Gregorian dates — of the period containing `anchor`
    (default today). Months and years follow `calendar`."""
    anchor = anchor or timezone.localdate()
    if period == "day":
        return anchor, anchor
    if period == "week":
        start = anchor - timedelta(days=anchor.weekday())  # Monday
        return start, start + timedelta(days=6)
    if calendar == "ethiopian" and period in ("month", "year"):
        ec = ethiopian.to_ethiopian(anchor)
        return (ethiopian.month_range(ec.year, ec.month) if period == "month"
                else ethiopian.year_range(ec.year))
    if period == "month":
        start = anchor.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, nxt - timedelta(days=1)
    if period == "year":
        return anchor.replace(month=1, day=1), anchor.replace(month=12, day=31)
    raise ValueError(f"Unknown period {period!r}")


def _bounds(first: date, last: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(first, time.min), tz),
            timezone.make_aware(datetime.combine(last + timedelta(days=1), time.min), tz))


def _sum(qs, field) -> Decimal:
    return (qs.aggregate(t=Sum(field))["t"] or ZERO).quantize(ZERO)


def _money(value) -> str:
    return str(Decimal(value).quantize(ZERO))


def _ec(value) -> str:
    return ethiopian.format_both(value, with_time=isinstance(value, datetime))


def _month_key(value, calendar: str) -> str:
    local = timezone.localtime(value).date() if isinstance(value, datetime) else value
    if calendar == "ethiopian":
        ec = ethiopian.to_ethiopian(local)
        return f"{ec.year}-{ec.month:02d}"
    return local.strftime("%Y-%m")


def _month_label(key: str, calendar: str) -> str:
    year, month = (int(part) for part in key.split("-"))
    return ethiopian.month_label(year, month) if calendar == "ethiopian" else key


def _sees_personal(user) -> bool:
    return user.has_erp_permission("view_personal_payments")


def _scope_orders(qs, user, filters):
    """Salespeople only ever see their own sales (D9)."""
    if user.role == "salesperson":
        qs = qs.filter(salesperson=user)
    for key, field in (("branch", "branch"), ("salesperson", "salesperson"),
                       ("customer", "customer"), ("order", "pk")):
        if filters.get(key):
            qs = qs.filter(**{field: filters[key]})
    return qs


# ---------------------------------------------------------------- sales

def sales_report(user, first: date, last: date, filters: dict | None = None,
                 calendar: str = "ethiopian") -> dict:
    filters = filters or {}
    start, end = _bounds(first, last)
    orders = _scope_orders(SalesOrder.objects.filter(
        fulfillment_status__in=BILLABLE_STATUSES, confirmed_at__gte=start,
        confirmed_at__lt=end), user, filters)
    lines = SalesOrderLine.objects.filter(order__in=orders)
    if filters.get("category"):
        lines = lines.filter(product__category=filters["category"])
    returns = SalesReturn.objects.filter(
        created_at__gte=start, created_at__lt=end,
        order__in=_scope_orders(SalesOrder.objects.filter(
            fulfillment_status__in=BILLABLE_STATUSES), user, filters))

    gross = _sum(lines, "line_total")
    returned = _sum(returns, "amount")
    by_receipt = {r["order__receipt_type"]: r["t"] for r in
                  lines.values("order__receipt_type").annotate(t=Sum("line_total"))}
    report = {
        "from": first, "to": last, "period_label": ethiopian.format_range(first, last),
        "calendar": calendar,
        "sales": _money(gross),
        "returns": _money(returned),
        "net_sales": _money(gross - returned),
        "transactions": orders.count(),
        "official_receipt": _money(by_receipt.get("official") or 0),
        "no_receipt": _money(by_receipt.get("none") or 0),
        "by_salesperson": [
            {"salesperson": r["order__salesperson__full_name"], "sales": _money(r["t"]),
             "transactions": r["n"]}
            for r in lines.values("order__salesperson__full_name")
            .annotate(t=Sum("line_total"), n=Count("order", distinct=True)).order_by("-t")],
        "by_branch": [
            {"branch": r["order__branch__code"], "sales": _money(r["t"]),
             "transactions": r["n"]}
            for r in lines.values("order__branch__code")
            .annotate(t=Sum("line_total"), n=Count("order", distinct=True)).order_by("-t")],
        "products": [
            {"code": r["product__code"], "name": r["product__name"], "qty": r["q"],
             "sales": _money(r["t"])}
            for r in lines.values("product__code", "product__name")
            .annotate(q=Sum("qty"), t=Sum("line_total")).order_by("-q", "product__code")],
    }
    if not filters.get("category"):
        # What the period's sales stand at now: paid so far vs still owed.
        total_now = _sum(orders, "total_amount")
        paid_now = _sum(active_allocations().filter(order__in=orders), "amount")
        report["paid"] = _money(paid_now)
        report["credit"] = _money(total_now - paid_now)
    report["best_sellers"] = report["products"][:10]
    report["received"] = payments_totals(user, first, last, filters)
    if (last - first).days > 31:
        report["by_month"] = _by_month(lines, returns, first, last, calendar)
    return report


def _calendar_months(first: date, last: date, calendar: str) -> list[str]:
    if calendar == "ethiopian":
        return [f"{y}-{m:02d}" for y, m in ethiopian.months_between(first, last)]
    keys, cursor = [], first.replace(day=1)
    while cursor <= last:
        keys.append(cursor.strftime("%Y-%m"))
        cursor = (cursor + timedelta(days=32)).replace(day=1)
    return keys


def _by_month(lines, returns, first: date, last: date, calendar: str) -> list[dict]:
    """Month-by-month breakdown for long periods (the yearly report: 13 Ethiopian months)."""
    sales = defaultdict(lambda: ZERO)
    count = defaultdict(set)
    for row in lines.values("order_id", "order__confirmed_at", "line_total"):
        key = _month_key(row["order__confirmed_at"], calendar)
        sales[key] += row["line_total"]
        count[key].add(row["order_id"])
    returned = defaultdict(lambda: ZERO)
    for row in returns.values("created_at", "amount"):
        returned[_month_key(row["created_at"], calendar)] += row["amount"]
    return [{"month": key, "label": _month_label(key, calendar), "sales": _money(sales[key]),
             "returns": _money(returned[key]),
             "net_sales": _money(sales[key] - returned[key]),
             "transactions": len(count[key])}
            for key in _calendar_months(first, last, calendar)]


# ---------------------------------------------------------------- payments

def _payments(user, first: date, last: date, filters: dict):
    start, end = _bounds(first, last)
    qs = Payment.objects.filter(status__in=VALID_PAYMENT_STATUSES, paid_at__gte=start,
                                paid_at__lt=end)
    if user.role == "salesperson":
        qs = qs.filter(Q(recorded_by=user) | Q(allocations__order__salesperson=user))
    if not _sees_personal(user):
        qs = qs.exclude(account__kind="personal")
    for key, field in (("customer", "customer"), ("account", "account"),
                       ("account_kind", "account__kind"), ("order", "allocations__order"),
                       ("branch", "allocations__order__branch")):
        if filters.get(key):
            qs = qs.filter(**{field: filters[key]})
    if filters.get("salesperson"):
        qs = qs.filter(Q(allocations__order__salesperson=filters["salesperson"])
                       | Q(allocations__isnull=True, recorded_by=filters["salesperson"]))
    return Payment.objects.filter(pk__in=qs.values("pk"))  # one row per payment


def payments_totals(user, first: date, last: date, filters: dict | None = None) -> dict:
    qs = _payments(user, first, last, filters or {})
    organization = _sum(qs.filter(account__kind="organization"), "amount")
    if not _sees_personal(user):
        return {"organization": _money(organization), "personal": None, "combined": None}
    personal = _sum(qs.filter(account__kind="personal"), "amount")
    return {"organization": _money(organization), "personal": _money(personal),
            "combined": _money(organization + personal)}


def payments_report(user, first: date, last: date, filters: dict | None = None,
                    group_by: str = "day", calendar: str = "ethiopian") -> dict:
    filters = filters or {}
    qs = _payments(user, first, last, filters).select_related("customer", "account",
                                                              "recorded_by")
    groups = defaultdict(lambda: {"organization": ZERO, "personal": ZERO})
    rows = []
    for p in qs.order_by("paid_at", "id"):
        local = timezone.localtime(p.paid_at).date()
        if group_by == "week":
            key = (local - timedelta(days=local.weekday())).isoformat()
        elif group_by == "month":
            key = _month_key(local, calendar)
        elif group_by == "year":
            key = (str(ethiopian.to_ethiopian(local).year) if calendar == "ethiopian"
                   else str(local.year))
        else:
            key = local.isoformat()
        groups[key][p.account.kind] += p.amount
        rows.append({"number": p.number, "paid_at": p.paid_at, "date_ec": _ec(p.paid_at),
                     "customer": p.customer.name,
                     "amount": _money(p.amount), "account": p.account.name,
                     "kind": p.account.kind, "method": p.method,
                     "receipt_number": p.receipt_number, "status": p.status,
                     "recorded_by": p.recorded_by.full_name})
    sees = _sees_personal(user)
    def label(key):
        if group_by == "month":
            return _month_label(key, calendar)
        if group_by in ("day", "week"):
            return ethiopian.format_both(date.fromisoformat(key))
        return key

    return {
        "from": first, "to": last, "period_label": ethiopian.format_range(first, last),
        "calendar": calendar,
        "totals": payments_totals(user, first, last, filters),
        "by_period": [{"period": key, "label": label(key),
                       "organization": _money(v["organization"]),
                       "personal": _money(v["personal"]) if sees else None,
                       "combined": _money(v["organization"] + v["personal"]) if sees else None}
                      for key, v in sorted(groups.items())],
        "payments": rows,
    }


# ---------------------------------------------------------------- credit

AGE_BUCKETS = (("0_30", 0, 30), ("31_60", 31, 60), ("61_90", 61, 90), ("over_90", 91, None))


def credit_report(user, first: date, last: date, filters: dict | None = None) -> dict:
    """Outstanding per customer, aged by how long each unpaid sale has been open (money not
    yet tied to a sale is applied to the oldest sales first), plus credit collected."""
    filters = filters or {}
    today = timezone.localdate()
    customers = Customer.objects.all()
    if filters.get("customer"):
        customers = customers.filter(pk=filters["customer"])
    if user.role == "salesperson":
        customers = customers.filter(orders__salesperson=user).distinct()
    rows, total = [], ZERO
    for customer in customers:
        balance = customer_balance(customer)
        if balance["outstanding"] <= 0:
            continue
        buckets = {name: ZERO for name, _, _ in AGE_BUCKETS}
        free = balance["unallocated"]
        orders = (SalesOrder.objects.filter(customer=customer,
                                            fulfillment_status__in=BILLABLE_STATUSES)
                  .order_by("confirmed_at", "id"))
        for order in orders:
            paid = _sum(active_allocations().filter(order=order), "amount")
            remaining = order.total_amount - paid
            covered = min(remaining, free)
            remaining, free = remaining - covered, free - covered
            if remaining <= 0:
                continue
            age = (today - timezone.localtime(order.confirmed_at).date()).days
            for name, low, high in AGE_BUCKETS:
                if age >= low and (high is None or age <= high):
                    buckets[name] += remaining
                    break
        total += balance["outstanding"]
        rows.append({"customer": customer.name, "shop_name": customer.shop_name,
                     "phone": customer.phone, "city": customer.city,
                     "credit_limit": (_money(customer.credit_limit)
                                      if customer.credit_limit is not None else None),
                     "outstanding": _money(balance["outstanding"]),
                     **{k: _money(v) for k, v in buckets.items()}})
    rows.sort(key=lambda r: Decimal(r["outstanding"]), reverse=True)
    start, end = _bounds(first, last)
    collected = active_allocations().filter(created_at__gte=start, created_at__lt=end,
                                            order__confirmed_at__lt=start)
    if not _sees_personal(user):
        collected = collected.exclude(payment__account__kind="personal")
    return {"from": first, "to": last, "period_label": ethiopian.format_range(first, last),
            "outstanding_total": _money(total),
            "credit_collected": _money(_sum(collected, "amount")), "customers": rows}


# ---------------------------------------------------------------- stock

def stock_report(user, filters: dict | None = None) -> dict:
    filters = filters or {}
    products = products_with_total().filter(is_active=True).select_related("unit")
    if filters.get("category"):
        products = products.filter(category=filters["category"])
    locations = matrix_locations()
    rows = []
    for row in stock_rows(products.order_by("code"), locations):
        product = row["product"]
        rows.append({
            "code": product.code, "name": product.name, "unit": product.unit.symbol,
            "stock": {code: cell["on_hand"] for code, cell in row["stock"].items()},
            "display": sum(c["display"] for c in row["stock"].values()),
            "damaged": sum(c["damaged"] for c in row["stock"].values()),
            "in_transit": row["in_transit"], "total": row["total"],
            "total_new": row["total_new"], "min_stock": product.min_stock,
            "low_stock": 0 < product.min_stock and row["total_new"] < product.min_stock,
        })
    return {"locations": [loc.code for loc in locations], "products": rows}


def movements_report(user, first: date, last: date, filters: dict | None = None) -> dict:
    from apps.inventory.selectors import movements_for_user

    filters = filters or {}
    start, end = _bounds(first, last)
    qs = movements_for_user(user).filter(occurred_at__gte=start, occurred_at__lt=end)
    if filters.get("product"):
        qs = qs.filter(product=filters["product"])
    if filters.get("location"):
        qs = qs.filter(Q(from_location=filters["location"]) | Q(to_location=filters["location"]))
    if filters.get("type"):
        qs = qs.filter(type=filters["type"])
    rows = [{"number": m.number, "occurred_at": m.occurred_at, "date_ec": _ec(m.occurred_at),
             "type": m.type,
             "condition": m.condition, "product": m.product.code, "qty": m.qty,
             "from": m.from_location.code if m.from_location else None,
             "to": m.to_location.code if m.to_location else None,
             "customer": m.customer.name if m.customer else None,
             "transaction": m.transaction_number, "reference": m.reference_id,
             "person": m.person.full_name}
            for m in qs.order_by("occurred_at", "id")]
    return {"from": first, "to": last, "period_label": ethiopian.format_range(first, last),
            "count": len(rows), "movements": rows}


def open_requests_report(user, filters: dict | None = None) -> dict:
    from apps.requests.selectors import requests_for_user

    now = timezone.now()
    rows = []
    for r in (requests_for_user(user).filter(status__in=OPEN_STATUSES)
              .prefetch_related("lines").order_by("created_at")):
        remaining = sum(ln.qty_remaining for ln in r.lines.all())
        rows.append({"number": r.number, "status": r.status,
                     "branch": r.requesting_location.code, "source": r.source_location.code,
                     "customer": r.customer.name if r.customer else None,
                     "salesperson": r.salesperson.full_name, "created_at": r.created_at,
                     "date_ec": _ec(r.created_at),
                     "waiting_hours": round((now - r.created_at).total_seconds() / 3600, 1),
                     "units_remaining": remaining})
    return {"count": len(rows), "requests": rows}


def unverified_payments_report(user, filters: dict | None = None) -> dict:
    qs = (Payment.objects.filter(status="unverified")
          .select_related("customer", "account", "recorded_by").order_by("paid_at"))
    if not _sees_personal(user):
        qs = qs.exclude(account__kind="personal")
    rows = [{"id": p.pk, "number": p.number, "paid_at": p.paid_at, "date_ec": _ec(p.paid_at),
             "customer": p.customer.name,
             "amount": _money(p.amount), "account": p.account.name, "kind": p.account.kind,
             "receipt_number": p.receipt_number, "recorded_by": p.recorded_by.full_name}
            for p in qs]
    return {"count": len(rows), "total": _money(sum((Decimal(r["amount"]) for r in rows), ZERO)),
            "payments": rows}
