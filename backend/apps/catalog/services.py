from decimal import Decimal

from django.db import transaction

from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError

from .models import PriceHistory, PriceType, Product

_AUDITED_FIELDS = ("code", "name", "category_id", "unit_id", "min_stock", "is_active")
_PRICE_FIELD = {PriceType.SELLING: "selling_price", PriceType.WHOLESALE: "wholesale_price"}
# Audit keys: "price" for the selling price (kept from Phase 1), "wholesale_price" otherwise.
_AUDIT_KEY = {PriceType.SELLING: "price", PriceType.WHOLESALE: "wholesale_price"}


def _snapshot(product: Product) -> dict:
    return {field: getattr(product, field) for field in _AUDITED_FIELDS}


def _check_prices(selling: Decimal, wholesale: Decimal | None):
    if selling <= 0:
        raise BusinessRuleError("invalid_price", "Price must be greater than zero.")
    if wholesale is not None:
        if wholesale <= 0:
            raise BusinessRuleError("invalid_price", "Wholesale price must be greater than zero.")
        if wholesale > selling:
            raise BusinessRuleError(
                "wholesale_above_selling",
                f"Wholesale price {wholesale} cannot be higher than the selling price {selling}.")


@transaction.atomic
def create_product(*, user, selling_price: Decimal, wholesale_price: Decimal | None = None,
                   **fields) -> Product:
    _check_prices(selling_price, wholesale_price)
    product = Product.objects.create(created_by=user, selling_price=selling_price,
                                     wholesale_price=wholesale_price, **fields)
    audit_log(actor=user, action="product_created", obj=product,
              after={**_snapshot(product), "price": str(product.selling_price),
                     "wholesale_price": (str(product.wholesale_price)
                                         if product.wholesale_price is not None else None)})
    return product


@transaction.atomic
def update_product(*, user, product: Product, **fields) -> Product:
    """Edit product details. Prices change only through change_price()."""
    if {"selling_price", "wholesale_price"} & set(fields):
        raise BusinessRuleError("price_read_only", "Use change-price to change a price.")
    product = Product.objects.select_for_update().get(pk=product.pk)
    before = _snapshot(product)
    for name, value in fields.items():
        setattr(product, name, value)
    product.save()
    after = _snapshot(product)
    changed = {k: v for k, v in after.items() if before[k] != v}
    if changed:
        audit_log(actor=user, action="product_updated", obj=product,
                  before={k: before[k] for k in changed}, after=changed)
    return product


@transaction.atomic
def change_price(*, product: Product, new_price: Decimal, user, reason: str = "",
                 price_type: str = PriceType.SELLING) -> Product:
    """Change the selling or the wholesale price; writes PriceHistory and the audit log.

    Sales already made keep the price they were made at.
    """
    if price_type not in _PRICE_FIELD:
        raise BusinessRuleError("invalid_price_type", "Choose the selling or wholesale price.")
    field = _PRICE_FIELD[price_type]
    product = Product.objects.select_for_update().get(pk=product.pk)
    old = getattr(product, field)
    if new_price == old:
        raise BusinessRuleError("price_unchanged", f"{product.code} is already {old}.")
    selling = new_price if price_type == PriceType.SELLING else product.selling_price
    wholesale = new_price if price_type == PriceType.WHOLESALE else product.wholesale_price
    _check_prices(selling, wholesale)

    setattr(product, field, new_price)
    product.save(update_fields=[field, "updated_at"])
    PriceHistory.objects.create(product=product, price_type=price_type, old_price=old,
                                new_price=new_price, changed_by=user, reason=reason)
    key = _AUDIT_KEY[price_type]
    audit_log(actor=user, action="price_change", obj=product,
              before={key: str(old) if old is not None else None},
              after={key: str(new_price)}, reason=reason)
    return product
