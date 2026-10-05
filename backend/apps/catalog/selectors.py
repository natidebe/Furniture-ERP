from .models import Product


def products():
    return Product.objects.select_related("category", "unit")


def product_by_code(code: str) -> Product | None:
    return products().filter(code=code.strip().upper()).first()
