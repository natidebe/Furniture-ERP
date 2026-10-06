from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Channel(models.TextChoices):
    WALK_IN = "walk_in"
    PHONE = "phone"


class FulfillmentStatus(models.TextChoices):
    DRAFT = "draft"                            # walk-in, being entered
    PENDING = "pending"                        # phone order, not confirmed yet
    CONFIRMED = "confirmed"
    PREPARED = "prepared"                      # storekeeper has the goods ready
    PARTIALLY_RELEASED = "partially_released"  # some goods handed to the customer
    RELEASED = "released"                      # every unit handed to the customer
    CANCELLED = "cancelled"                    # stopped before any handover
    VOIDED = "voided"                          # a wrong sale, reversed (D6)


EDITABLE_STATUSES = (FulfillmentStatus.DRAFT, FulfillmentStatus.PENDING)
# Orders that count as sales and in the customer's balance.
BILLABLE_STATUSES = (FulfillmentStatus.CONFIRMED, FulfillmentStatus.PREPARED,
                     FulfillmentStatus.PARTIALLY_RELEASED, FulfillmentStatus.RELEASED)
CLOSED_STATUSES = (FulfillmentStatus.CANCELLED, FulfillmentStatus.VOIDED)


class OrderPaymentStatus(models.TextChoices):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class ReceiptType(models.TextChoices):
    OFFICIAL = "official"  # paid only into Organization accounts, one receipt per payment
    NONE = "none"


class SalesOrder(TimeStampedModel):
    """A sale. Its number (SO-…) is the master transaction number (D4)."""

    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT,
                                 related_name="orders")
    branch = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                               related_name="+")
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="orders")
    channel = models.CharField(max_length=10, choices=Channel.choices)
    fulfillment_status = models.CharField(max_length=20, choices=FulfillmentStatus.choices,
                                          db_index=True)
    payment_status = models.CharField(max_length=10, choices=OrderPaymentStatus.choices,
                                      default=OrderPaymentStatus.UNPAID, db_index=True)
    receipt_type = models.CharField(max_length=10, choices=ReceiptType.choices)
    # Σ line totals − Σ returns; kept up to date by sales.services.
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    confirmed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                     on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)  # cancelled or voided
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="+")
    close_reason = models.TextField(blank=True)
    replaces = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="replaced_by")

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.CheckConstraint(condition=Q(total_amount__gte=0),
                                              name="order_total_not_negative")]

    def __str__(self):
        return self.number

    @property
    def is_billable(self) -> bool:
        return self.fulfillment_status in BILLABLE_STATUSES


class SalesOrderLine(models.Model):
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=14, decimal_places=2)  # snapshot (D11)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)  # line amount
    line_total = models.DecimalField(max_digits=14, decimal_places=2)
    # Where the goods come from: the branch (or its sub-store) = sold on confirmation;
    # a releasing warehouse (Pawlos) = a stock request.
    source_location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                        related_name="+")
    qty_released = models.PositiveIntegerField(default=0)  # handed to the customer
    # Arrived at the branch from the warehouse and held there for this sale.
    qty_awaiting = models.PositiveIntegerField(default=0)
    qty_returned = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "product"],
                                    name="one_line_per_product_per_order"),
            models.CheckConstraint(condition=Q(qty__gt=0), name="order_line_qty_positive"),
            models.CheckConstraint(condition=Q(discount__gte=0),
                                   name="order_line_discount_not_negative"),
            models.CheckConstraint(condition=Q(line_total__gte=0),
                                   name="order_line_total_not_negative"),
            models.CheckConstraint(condition=Q(qty_released__lte=F("qty")),
                                   name="order_line_released_within_qty"),
            models.CheckConstraint(
                condition=Q(qty_awaiting__lte=F("qty") - F("qty_released")),
                name="order_line_awaiting_within_open_qty"),
            models.CheckConstraint(condition=Q(qty_returned__lte=F("qty_released")),
                                   name="order_line_returned_within_released"),
        ]

    def __str__(self):
        return f"{self.order_id}: {self.qty} × {self.product_id}"

    @property
    def qty_open(self) -> int:
        """Still to hand over to the customer."""
        return self.qty - self.qty_released


class DeliveryNote(models.Model):
    """One handover of goods to the customer (the digital delivery paper)."""

    number = models.CharField(max_length=20, unique=True)
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT,
                              related_name="delivery_notes")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                 related_name="+")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                  related_name="+")
    issued_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-issued_at", "-id"]

    def __str__(self):
        return self.number


class DeliveryNoteLine(models.Model):
    note = models.ForeignKey(DeliveryNote, on_delete=models.PROTECT, related_name="lines")
    order_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT,
                                   related_name="delivery_lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty = models.PositiveIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0),
                                              name="delivery_line_qty_positive")]


class SalesReturn(models.Model):
    """Goods the customer brought back. Lowers the order total by `amount`."""

    number = models.CharField(max_length=20, unique=True)
    order = models.ForeignKey(SalesOrder, on_delete=models.PROTECT, related_name="returns")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                 related_name="+")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.number


class SalesReturnLine(models.Model):
    sales_return = models.ForeignKey(SalesReturn, on_delete=models.PROTECT,
                                     related_name="lines")
    order_line = models.ForeignKey(SalesOrderLine, on_delete=models.PROTECT,
                                   related_name="return_lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0),
                                              name="return_line_qty_positive")]
