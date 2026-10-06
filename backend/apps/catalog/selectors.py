from decimal import Decimal

from .models import Product


def products():
    return Product.objects.select_related("category", "unit")


def product_by_code(code: str) -> Product | None:
    return products().filter(code=code.strip().upper()).first()


def price_for(product: Product, customer=None) -> Decimal:
    """The unit price a sale uses (Q15): resellers pay the wholesale price when the product
    has one; everyone else, and resellers when it has none, pays the selling price."""
    if customer is not None and customer.type == "reseller" and product.wholesale_price:
        return product.wholesale_price
    return product.selling_price
