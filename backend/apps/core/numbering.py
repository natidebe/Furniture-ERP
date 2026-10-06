from django.db import transaction
from django.utils import timezone

from .models import DocumentSequence

# Document prefixes used across the project.
SALES_ORDER = "SO"
DELIVERY_NOTE = "DN"
STOCK_REQUEST = "SR"
STOCK_RELEASE = "SRL"
TRANSFER = "TR"
GOODS_RECEIPT = "GR"
ADJUSTMENT = "ADJ"
PAYMENT = "PAY"
MOVEMENT = "MV"
SALES_RETURN = "RET"
CONDITION_CHANGE = "CC"


def next_number(prefix: str) -> str:
    """Return e.g. 'SO-2026-00125'. Must be called inside transaction.atomic().

    Gapless: the sequence row stays locked until the caller's transaction commits,
    and a rollback also rolls back the increment.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("next_number() must be called inside transaction.atomic()")
    year = timezone.localdate().year
    # Create the year's row without racing: on Postgres a concurrent insert of the same
    # (prefix, year) waits and then does nothing, instead of raising IntegrityError.
    DocumentSequence.objects.bulk_create(
        [DocumentSequence(prefix=prefix, year=year)], ignore_conflicts=True
    )
    seq = DocumentSequence.objects.select_for_update().get(prefix=prefix, year=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"{prefix}-{year}-{seq.last_number:05d}"
