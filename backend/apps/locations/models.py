from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import ActiveModel


class LocationType(models.TextChoices):
    SHOP = "shop"
    WAREHOUSE = "warehouse"
    SUB_STORE = "sub_store"


class Location(ActiveModel):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=LocationType.choices)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="children")
    can_sell = models.BooleanField(default=False)
    can_release = models.BooleanField(default=False)

    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)
