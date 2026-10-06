from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import ActiveModel

WALK_IN_CUSTOMER_NAME = "Walk-in Customer"


class CustomerType(models.TextChoices):
    WALK_IN = "walk_in"
    RESELLER = "reseller"
    OUT_OF_CITY = "out_of_city"


class Customer(ActiveModel):
    """Created in Phase 2 because stock movements and requests reference customers.
    Balances, statements and endpoints come in Phase 3."""

    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30, blank=True, db_index=True)
    shop_name = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    type = models.CharField(max_length=20, choices=CustomerType.choices,
                            default=CustomerType.WALK_IN)
    credit_allowed = models.BooleanField(default=False)
    # Null means no limit (only meaningful when credit_allowed is true).
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(credit_limit__isnull=True) | models.Q(credit_limit__gte=0),
                name="customer_credit_limit_not_negative"),
        ]

    def __str__(self):
        return f"{self.name} ({self.shop_name})" if self.shop_name else self.name
