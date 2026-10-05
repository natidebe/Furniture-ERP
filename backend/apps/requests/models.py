from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class RequestStatus(models.TextChoices):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_RELEASED = "partially_released"
    RELEASED = "released"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    CLOSED = "closed"


# Statuses whose unreleased quantities are still reserved at the source location.
OPEN_STATUSES = (RequestStatus.PENDING, RequestStatus.ACKNOWLEDGED,
                 RequestStatus.PARTIALLY_RELEASED)


class DestinationType(models.TextChoices):
    BRANCH = "branch"                  # Pawlos → requesting branch (a transfer)
    CUSTOMER_PICKUP = "customer_pickup"  # the customer collects at Pawlos (a sale)


class StockRequest(models.Model):
    """A request for stock from the warehouse — the digital delivery paper.

    The status is changed only by requests.services; there is no way to release stock
    without one of these in an open status.
    """

    number = models.CharField(max_length=20, unique=True)
    requesting_location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                            related_name="+")
    source_location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                        related_name="+")
    # D4: the order's SO-… number once sales exist (Phase 3), otherwise this request's number.
    transaction_number = models.CharField(max_length=20, db_index=True)
    customer = models.ForeignKey("customers.Customer", null=True, blank=True,
                                 on_delete=models.PROTECT, related_name="stock_requests")
    reference = models.CharField(max_length=100, blank=True)  # customer / order reference
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="stock_requests")
    status = models.CharField(max_length=20, choices=RequestStatus.choices,
                              default=RequestStatus.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                        on_delete=models.PROTECT, related_name="+")
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.TextField(blank=True)  # reject / cancel / close reason

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.number

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


class StockRequestLine(models.Model):
    request = models.ForeignKey(StockRequest, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty_requested = models.PositiveIntegerField()
    qty_released = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["request", "product"],
                                    name="one_line_per_product_per_request"),
            models.CheckConstraint(condition=Q(qty_requested__gt=0),
                                   name="request_qty_positive"),
            models.CheckConstraint(condition=Q(qty_released__lte=F("qty_requested")),
                                   name="released_within_requested"),
        ]

    @property
    def qty_remaining(self) -> int:
        return self.qty_requested - self.qty_released


class StockRelease(models.Model):
    """What the storekeeper actually took out, against one request."""

    number = models.CharField(max_length=20, unique=True)
    request = models.ForeignKey(StockRequest, on_delete=models.PROTECT, related_name="releases")
    transaction_number = models.CharField(max_length=20, db_index=True)
    destination_type = models.CharField(max_length=20, choices=DestinationType.choices)
    transfer = models.OneToOneField("inventory.StockTransfer", null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="release")
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    released_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-released_at", "-id"]

    def __str__(self):
        return self.number


class StockReleaseLine(models.Model):
    release = models.ForeignKey(StockRelease, on_delete=models.PROTECT, related_name="lines")
    request_line = models.ForeignKey(StockRequestLine, on_delete=models.PROTECT,
                                     related_name="release_lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty = models.PositiveIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0),
                                              name="release_line_qty_positive")]
