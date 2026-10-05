from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import ActiveModel


class Category(ActiveModel):
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="children")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=10, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.symbol


class Product(ActiveModel):
    """A product the business sells. There is deliberately no cost, purchase price or profit."""

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products")
    # Changed only through services.change_price(), which records PriceHistory.
    selling_price = models.DecimalField(max_digits=14, decimal_places=2)
    min_stock = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(condition=models.Q(selling_price__gt=0),
                                   name="product_price_positive"),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="price_history")
    old_price = models.DecimalField(max_digits=14, decimal_places=2)
    new_price = models.DecimalField(max_digits=14, decimal_places=2)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    changed_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-changed_at", "-id"]
        verbose_name_plural = "price history"

    def __str__(self):
        return f"{self.product.code}: {self.old_price} → {self.new_price}"
