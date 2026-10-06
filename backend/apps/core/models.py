from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name="+",
    )

    class Meta:
        abstract = True


class ActiveModel(TimeStampedModel):
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class SystemSettings(models.Model):
    """Settings the owner changes in the app (one row). Read with core.services.get_settings."""

    max_salesperson_discount_pct = models.DecimalField(max_digits=5, decimal_places=2,
                                                       default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")

    class Meta:
        verbose_name_plural = "system settings"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_salesperson_discount_pct__gte=0,
                                   max_salesperson_discount_pct__lte=100),
                name="discount_pct_between_0_and_100"),
        ]

    def __str__(self):
        return "System settings"


class DocumentSequence(models.Model):
    """Last number issued per document prefix and year. Only touched by next_number()."""

    prefix = models.CharField(max_length=10)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["prefix", "year"], name="unique_sequence_per_year"),
        ]

    def __str__(self):
        return f"{self.prefix}-{self.year}: {self.last_number}"
