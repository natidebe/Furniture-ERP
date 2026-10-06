from celery import shared_task
from django.db import transaction


@shared_task
def check_low_stock(product_id: int) -> bool:
    """Queued after every stock change. Alerts admins and the warehouse storekeeper when the
    product's sellable company stock (new pieces, all locations and in transit — D7, D15) is
    below its minimum; at most once per product per day. Returns True when it alerted."""
    from apps.notifications.services import notify, once_today

    from .selectors import products_with_total

    product = (products_with_total().select_related("unit").filter(pk=product_id).first())
    if product is None or not product.min_stock or product.total_new >= product.min_stock:
        return False
    with transaction.atomic():
        if not once_today(f"low_stock:{product_id}"):
            return False
        notify("stock.low", product, total_new=product.total_new)
    return True


@shared_task
def nightly_stock_check() -> int:
    """02:00: compare every balance with the ledger; alert admins if anything differs."""
    from apps.notifications.services import notify

    from .selectors import balance_mismatches

    mismatches = balance_mismatches()
    if mismatches:
        with transaction.atomic():
            notify("stock.mismatch", None, count=len(mismatches))
    return len(mismatches)
