from celery import shared_task


@shared_task
def check_low_stock(product_id: int) -> None:
    """Queued after every movement. Stub until Phase 4.4, which compares the company total
    with Product.min_stock and notifies admins and the storekeeper once per day."""
    return None
