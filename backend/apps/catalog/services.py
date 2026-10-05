from decimal import Decimal

from django.db import transaction

from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError

from .models import PriceHistory, Product

_AUDITED_FIELDS = ("code", "name", "category_id", "unit_id", "min_stock", "is_active")


def _snapshot(product: Product) -> dict:
    return {field: getattr(product, field) for field in _AUDITED_FIELDS}


@transaction.atomic
def create_product(*, user, selling_price: Decimal, **fields) -> Product:
    if selling_price <= 0:
        raise BusinessRuleError("invalid_price", "Price must be greater than zero.")
    product = Product.objects.create(created_by=user, selling_price=selling_price, **fields)
    audit_log(actor=user, action="product_created", obj=product,
              after={**_snapshot(product), "price": str(product.selling_price)})
    return product


@transaction.atomic
def update_product(*, user, product: Product, **fields) -> Product:
    """Edit product details. The price is changed only through change_price()."""
    if "selling_price" in fields:
        raise BusinessRuleError("price_read_only", "Use change-price to change the price.")
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
def change_price(*, product: Product, new_price: Decimal, user, reason: str = "") -> Product:
    if new_price <= 0:
        raise BusinessRuleError("invalid_price", "Price must be greater than zero.")
    product = Product.objects.select_for_update().get(pk=product.pk)
    old = product.selling_price
    if new_price == old:
        raise BusinessRuleError("price_unchanged", f"{product.code} already costs {old}.")
    product.selling_price = new_price
    product.save(update_fields=["selling_price", "updated_at"])
    PriceHistory.objects.create(product=product, old_price=old, new_price=new_price,
                                changed_by=user, reason=reason)
    audit_log(actor=user, action="price_change", obj=product,
              before={"price": str(old)}, after={"price": str(new_price)}, reason=reason)
    return product
