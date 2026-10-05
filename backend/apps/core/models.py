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
