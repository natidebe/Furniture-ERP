"""One search box for everything (the requirement "Search"): products, customers, sales,
delivery notes, stock requests and payments — each limited to what the user may see."""

from django.db.models import Q

from apps.catalog.models import Product
from apps.customers.models import Customer
from apps.customers.selectors import customer_balance
from apps.inventory.selectors import matrix_locations, stock_rows
from apps.payments.api.serializers import payment_dict
from apps.payments.selectors import payments_for_user
from apps.requests.selectors import requests_for_user
from apps.sales.selectors import delivery_notes_for_user, orders_for_user

LIMIT = 10


def _dated(qs, field, filters):
    if filters.get("from"):
        qs = qs.filter(**{f"{field}__date__gte": filters["from"]})
    if filters.get("to"):
        qs = qs.filter(**{f"{field}__date__lte": filters["to"]})
    return qs


def search(q: str, user, filters: dict | None = None) -> dict:
    filters = filters or {}
    q = (q or "").strip()
    if len(q) < 2:
        return {"query": q, "exact": None, "products": [], "customers": [], "orders": [],
                "delivery_notes": [], "stock_requests": [], "payments": []}
    upper = q.upper()

    products = list(Product.objects.filter(is_active=True)
                    .filter(Q(code__icontains=q) | Q(name__icontains=q))
                    .order_by("code")[:LIMIT])
    products.sort(key=lambda p: p.code != upper)  # an exact code first
    locations = matrix_locations()
    product_rows = [{
        "id": row["product"].pk, "code": row["product"].code, "name": row["product"].name,
        "selling_price": str(row["product"].selling_price),
        "wholesale_price": (str(row["product"].wholesale_price)
                            if row["product"].wholesale_price is not None else None),
        "stock": {code: cell["on_hand"] for code, cell in row["stock"].items()},
        "in_transit": row["in_transit"], "total": row["total"],
    } for row in stock_rows(products, locations)]

    customers = []
    if user.role != "storekeeper":
        for c in Customer.objects.filter(Q(name__icontains=q) | Q(phone__icontains=q)
                                         | Q(shop_name__icontains=q))[:LIMIT]:
            customers.append({"id": c.pk, "name": c.name, "shop_name": c.shop_name,
                              "phone": c.phone, "city": c.city, "type": c.type,
                              "outstanding": str(customer_balance(c)["outstanding"])})

    orders = orders_for_user(user).filter(Q(number__icontains=q) | Q(customer__name__icontains=q)
                                          | Q(customer__phone__icontains=q))
    if filters.get("salesperson"):
        orders = orders.filter(salesperson=filters["salesperson"])
    if filters.get("branch"):
        orders = orders.filter(branch=filters["branch"])
    orders = _dated(orders, "created_at", filters)

    notes = _dated(delivery_notes_for_user(user).filter(number__icontains=q), "issued_at",
                   filters)
    requests = _dated(requests_for_user(user).filter(number__icontains=q), "created_at",
                      filters)
    payments = _dated(payments_for_user(user).filter(Q(number__icontains=q)
                                                     | Q(receipt_number__icontains=q)),
                      "paid_at", filters)

    exact = None
    for kind, qs in (("order", orders), ("delivery_note", notes), ("stock_request", requests),
                     ("payment", payments)):
        hit = qs.filter(number=upper).first()
        if hit:
            exact = {"kind": kind, "id": hit.pk, "number": hit.number}
            break
    if exact is None and products and products[0].code == upper:
        exact = {"kind": "product", "id": products[0].pk, "number": products[0].code}

    return {
        "query": q,
        "exact": exact,
        "products": product_rows,
        "customers": customers,
        "orders": [{"id": o.pk, "number": o.number, "customer": o.customer.name,
                    "salesperson": o.salesperson.full_name, "branch": o.branch.code,
                    "total": str(o.total_amount), "status": o.fulfillment_status,
                    "payment_status": o.payment_status, "created_at": o.created_at}
                   for o in orders.order_by("-created_at")[:LIMIT]],
        "delivery_notes": [{"id": n.pk, "number": n.number, "order": n.order.number,
                            "location": n.location.code, "issued_at": n.issued_at}
                           for n in notes.order_by("-issued_at")[:LIMIT]],
        "stock_requests": [{"id": r.pk, "number": r.number, "status": r.status,
                            "branch": r.requesting_location.code, "created_at": r.created_at}
                           for r in requests.order_by("-created_at")[:LIMIT]],
        "payments": [payment_dict(p, user) for p in payments.order_by("-paid_at")[:LIMIT]],
    }
