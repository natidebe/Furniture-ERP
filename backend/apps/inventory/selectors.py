from collections import defaultdict

from django.db.models import F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from apps.catalog.models import Product
from apps.locations.models import Location

from .models import TRANSIT_CODE, Condition, StockBalance, StockConditionChange, StockMovement


def transit_location() -> Location:
    return Location.objects.get(code=TRANSIT_CODE)


def matrix_locations() -> list[Location]:
    """Columns for stock views: active locations plus any inactive one still holding stock,
    in setup order (Piassa, Underground, Denbel, Pawlos), with In Transit last."""
    holding = StockBalance.objects.filter(on_hand__gt=0).values("location_id")
    locations = Location.objects.filter(Q(is_active=True) | Q(pk__in=holding))
    return sorted(locations, key=lambda loc: (loc.code == TRANSIT_CODE, loc.pk))


def balances():
    return StockBalance.objects.select_related("product", "location")


def products_with_total():
    """Products annotated with `total_on_hand` across every location, including transit (D7),
    and `total_new`: the same without display and damaged pieces (what can be sold as new)."""
    per_product = StockBalance.objects.filter(product=OuterRef("pk")).values("product")
    total = per_product.annotate(t=Sum("on_hand")).values("t")
    new = per_product.annotate(t=Sum(F("on_hand") - F("display") - F("damaged"))).values("t")
    return Product.objects.annotate(total_on_hand=Coalesce(Subquery(total), Value(0)),
                                    total_new=Coalesce(Subquery(new), Value(0)))


def low_stock_products():
    """Products whose sellable (new) company stock is below the admin-set minimum (D15)."""
    return products_with_total().filter(min_stock__gt=0, total_new__lt=F("min_stock"))


def stock_rows(products, locations) -> list[dict]:
    """One row per product: on hand per location code, in transit, and total (D7)."""
    products = list(products)
    found = defaultdict(dict)
    for bal in StockBalance.objects.filter(product__in=products):
        found[bal.product_id][bal.location_id] = bal
    rows = []
    for product in products:
        per_location = found[product.pk]
        stock = {}
        for loc in locations:
            bal = per_location.get(loc.pk)
            stock[loc.code] = {
                "on_hand": bal.on_hand if bal else 0,
                "reserved": bal.reserved if bal else 0,
                "display": bal.display if bal else 0,
                "damaged": bal.damaged if bal else 0,
                "available": bal.available if bal else 0,
            }
        rows.append({
            "product": product,
            "stock": stock,
            "in_transit": stock.get(TRANSIT_CODE, {}).get("on_hand", 0),
            "total": sum(b.on_hand for b in per_location.values()),
            "total_new": sum(b.new for b in per_location.values()),
        })
    return rows


def movements_for_user(user):
    """Storekeepers see movements at their own location; accountants and admins see all."""
    qs = StockMovement.objects.select_related("product", "from_location", "to_location",
                                              "customer", "person")
    role = getattr(user, "role", None)
    if role in ("accountant", "admin"):
        return qs
    if role == "storekeeper" and user.home_location_id:
        return qs.filter(Q(from_location=user.home_location_id)
                         | Q(to_location=user.home_location_id))
    return qs.none()


# ---------------------------------------------------------------- ledger checks

def expected_on_hand() -> dict[tuple[int, int], int]:
    """(product_id, location_id) → on hand recomputed from every movement."""
    result: dict[tuple[int, int], int] = defaultdict(int)
    for row in (StockMovement.objects.filter(to_location__isnull=False)
                .values("product_id", "to_location_id").annotate(q=Sum("qty"))):
        result[(row["product_id"], row["to_location_id"])] += row["q"]
    for row in (StockMovement.objects.filter(from_location__isnull=False)
                .values("product_id", "from_location_id").annotate(q=Sum("qty"))):
        result[(row["product_id"], row["from_location_id"])] -= row["q"]
    return dict(result)


def expected_reserved() -> dict[tuple[int, int], int]:
    """(product_id, location_id) → stock held: what open requests still hold at their source,
    plus goods that arrived at a branch for a sale and wait for the customer."""
    from apps.requests.models import OPEN_STATUSES, StockRequestLine
    from apps.sales.models import BILLABLE_STATUSES, SalesOrderLine

    result: dict[tuple[int, int], int] = defaultdict(int)
    rows = (StockRequestLine.objects.filter(request__status__in=OPEN_STATUSES)
            .values("product_id", "request__source_location_id")
            .annotate(q=Sum(F("qty_requested") - F("qty_released"))))
    for row in rows:
        if row["q"]:
            result[(row["product_id"], row["request__source_location_id"])] += row["q"]
    held = (SalesOrderLine.objects.filter(qty_awaiting__gt=0,
                                          order__fulfillment_status__in=BILLABLE_STATUSES)
            .values("product_id", "order__branch_id").annotate(q=Sum("qty_awaiting")))
    for row in held:
        result[(row["product_id"], row["order__branch_id"])] += row["q"]
    return dict(result)


def expected_condition(condition: str) -> dict[tuple[int, int], int]:
    """(product_id, location_id) → display or damaged pieces, from movements carrying that
    condition and the condition changes (D15)."""
    result: dict[tuple[int, int], int] = defaultdict(int)
    moves = StockMovement.objects.filter(condition=condition)
    for row in (moves.filter(to_location__isnull=False)
                .values("product_id", "to_location_id").annotate(q=Sum("qty"))):
        result[(row["product_id"], row["to_location_id"])] += row["q"]
    for row in (moves.filter(from_location__isnull=False)
                .values("product_id", "from_location_id").annotate(q=Sum("qty"))):
        result[(row["product_id"], row["from_location_id"])] -= row["q"]
    for field, sign in (("to_condition", 1), ("from_condition", -1)):
        for row in (StockConditionChange.objects.filter(**{field: condition})
                    .values("product_id", "location_id").annotate(q=Sum("qty"))):
            result[(row["product_id"], row["location_id"])] += sign * row["q"]
    return dict(result)


FIELDS = ("on_hand", "reserved", "display", "damaged")


def balance_mismatches() -> list[dict]:
    """Every balance whose counts differ from what the ledger says."""
    expected = {"on_hand": expected_on_hand(), "reserved": expected_reserved(),
                "display": expected_condition(Condition.DISPLAY),
                "damaged": expected_condition(Condition.DAMAGED)}
    stored = {(b.product_id, b.location_id): b for b in StockBalance.objects.all()}
    keys = set(stored).union(*expected.values())
    mismatches = []
    for key in sorted(keys):
        bal = stored.get(key)
        have = {f: getattr(bal, f) if bal else 0 for f in FIELDS}
        want = {f: expected[f].get(key, 0) for f in FIELDS}
        if have != want:
            mismatches.append({"product_id": key[0], "location_id": key[1],
                               **have, **{f"expected_{f}": want[f] for f in FIELDS}})
    return mismatches
