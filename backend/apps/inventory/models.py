from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError

TRANSIT_CODE = "TRANSIT"


class MovementType(models.TextChoices):
    RECEIPT = "receipt"            # import arrives (outside → location)
    TRANSFER_OUT = "transfer_out"  # location → in transit
    TRANSFER_IN = "transfer_in"    # in transit → location
    SALE = "sale"                  # location → customer
    RETURN = "return"              # customer → location
    ADJUSTMENT = "adjustment"      # count / damage / loss / found / opening balance
    REVERSAL = "reversal"          # cancels an earlier movement


class Condition(models.TextChoices):
    """Display and damaged pieces stay in the location's stock (and the company total) but are
    kept apart: never reserved for a request and never sold as new (D15)."""

    NEW = "new"
    DISPLAY = "display"
    DAMAGED = "damaged"


class StockMovementQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise BusinessRuleError("immutable", "Stock movements cannot be edited.")

    def delete(self):
        raise BusinessRuleError("immutable", "Stock movements cannot be deleted.")


class StockMovement(models.Model):
    """The stock ledger. Rows are only ever created (by inventory.services.post_movement).

    Direction is given by from/to: from only = stock leaves the company (sale), to only =
    stock enters (receipt, return), both = it moves between locations.
    """

    number = models.CharField(max_length=20, unique=True)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT,
                                related_name="movements")
    qty = models.PositiveIntegerField()
    from_location = models.ForeignKey("locations.Location", null=True, blank=True,
                                      on_delete=models.PROTECT, related_name="+")
    to_location = models.ForeignKey("locations.Location", null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    type = models.CharField(max_length=20, choices=MovementType.choices)
    condition = models.CharField(max_length=10, choices=Condition.choices,
                                 default=Condition.NEW)
    reference_type = models.CharField(max_length=30)   # "goods_receipt", "stock_release", ...
    reference_id = models.CharField(max_length=40)
    # D4: the master transaction number (SO-… once sales exist, or SR-… for a restock).
    transaction_number = models.CharField(max_length=20, blank=True, db_index=True)
    customer = models.ForeignKey("customers.Customer", null=True, blank=True,
                                 on_delete=models.PROTECT, related_name="movements")
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="+")
    note = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    reverses = models.OneToOneField("self", null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="reversed_by")

    objects = StockMovementQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(qty__gt=0), name="movement_qty_positive"),
            models.CheckConstraint(
                condition=Q(from_location__isnull=False) | Q(to_location__isnull=False),
                name="movement_has_a_location"),
        ]
        indexes = [models.Index(fields=["product", "occurred_at"])]

    def __str__(self):
        return f"{self.number} {self.type} {self.qty} × {self.product_id}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise BusinessRuleError("immutable", "Stock movements cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise BusinessRuleError("immutable", "Stock movements cannot be deleted.")


class StockBalance(models.Model):
    """Cached per-location balance; always equal to the sum of movements (rebuild checks it).

    `on_hand` counts every piece. Of those, `display` and `damaged` are kept apart (D15) and
    `reserved` is new stock held for requests or sales; `available` is new stock free to sell.
    """

    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT,
                                related_name="balances")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                 related_name="balances")
    on_hand = models.IntegerField(default=0)
    reserved = models.IntegerField(default=0)
    display = models.IntegerField(default=0)
    damaged = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["product", "location"],
                                    name="one_balance_per_product_location"),
            models.CheckConstraint(condition=Q(on_hand__gte=0), name="on_hand_not_negative"),
            models.CheckConstraint(condition=Q(reserved__gte=0), name="reserved_not_negative"),
            models.CheckConstraint(condition=Q(display__gte=0), name="display_not_negative"),
            models.CheckConstraint(condition=Q(damaged__gte=0), name="damaged_not_negative"),
            models.CheckConstraint(
                condition=Q(reserved__lte=F("on_hand") - F("display") - F("damaged")),
                name="reserved_within_new_stock"),
        ]

    def __str__(self):
        return f"{self.product_id}@{self.location_id}: {self.on_hand} ({self.reserved} reserved)"

    @property
    def new(self) -> int:
        return self.on_hand - self.display - self.damaged

    @property
    def available(self) -> int:
        """New stock free to sell or reserve."""
        return self.new - self.reserved

    def count_of(self, condition: str) -> int:
        return {Condition.NEW: self.new, Condition.DISPLAY: self.display,
                Condition.DAMAGED: self.damaged}[condition]


class StockConditionChange(models.Model):
    """Pieces moved between new, display and damaged at one location (D15). Immutable,
    like movements; the counts are rebuilt from these and the movements."""

    number = models.CharField(max_length=20, unique=True)
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                 related_name="+")
    qty = models.PositiveIntegerField()
    from_condition = models.CharField(max_length=10, choices=Condition.choices)
    to_condition = models.CharField(max_length=10, choices=Condition.choices)
    reason = models.CharField(max_length=255)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                               related_name="+")
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    objects = StockMovementQuerySet.as_manager()

    class Meta:
        ordering = ["-occurred_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(qty__gt=0), name="condition_change_qty_positive"),
            models.CheckConstraint(condition=~Q(from_condition=F("to_condition")),
                                   name="condition_change_changes_something"),
        ]

    def __str__(self):
        return f"{self.number} {self.qty} {self.from_condition}→{self.to_condition}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise BusinessRuleError("immutable", "Condition changes cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise BusinessRuleError("immutable", "Condition changes cannot be deleted.")


class GoodsReceipt(models.Model):
    number = models.CharField(max_length=20, unique=True)
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                 related_name="+")
    reference = models.CharField(max_length=100, blank=True)  # shipment / container / invoice
    received_at = models.DateTimeField(default=timezone.now)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-received_at", "-id"]

    def __str__(self):
        return self.number


class GoodsReceiptLine(models.Model):
    receipt = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty = models.PositiveIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(qty__gt=0),
                                              name="receipt_line_qty_positive")]


class AdjustmentReason(models.TextChoices):
    COUNT = "count"
    DAMAGE = "damage"
    LOSS = "loss"
    FOUND = "found"
    OPENING_BALANCE = "opening_balance"


class AdjustmentStatus(models.TextChoices):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class StockAdjustment(models.Model):
    number = models.CharField(max_length=20, unique=True)
    location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                 related_name="+")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    qty_delta = models.IntegerField()  # negative removes stock, positive adds
    condition = models.CharField(max_length=10, choices=Condition.choices,
                                 default=Condition.NEW)  # e.g. write off damaged pieces
    reason = models.CharField(max_length=20, choices=AdjustmentReason.choices)
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=AdjustmentStatus.choices,
                              default=AdjustmentStatus.PROPOSED)
    proposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="+")
    proposed_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=255, blank=True)
    movement = models.OneToOneField(StockMovement, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="adjustment")

    class Meta:
        ordering = ["-proposed_at", "-id"]
        constraints = [models.CheckConstraint(condition=~Q(qty_delta=0),
                                              name="adjustment_delta_not_zero")]

    def __str__(self):
        return self.number


class TransferStatus(models.TextChoices):
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"


class StockTransfer(models.Model):
    number = models.CharField(max_length=20, unique=True)
    from_location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                      related_name="+")
    to_location = models.ForeignKey("locations.Location", on_delete=models.PROTECT,
                                    related_name="+")
    status = models.CharField(max_length=12, choices=TransferStatus.choices,
                              default=TransferStatus.IN_TRANSIT)
    transaction_number = models.CharField(max_length=20, blank=True, db_index=True)
    stock_request = models.ForeignKey("requests.StockRequest", null=True, blank=True,
                                      on_delete=models.PROTECT, related_name="transfers")
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                related_name="+")
    sent_at = models.DateTimeField(auto_now_add=True)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    received_at = models.DateTimeField(null=True, blank=True)
    # Filled when fewer units arrive than were sent; the shortfall stays in TRANSIT until an
    # approved adjustment explains it.
    discrepancy_note = models.TextField(blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-sent_at", "-id"]

    def __str__(self):
        return self.number

    @property
    def has_discrepancy(self) -> bool:
        return bool(self.discrepancy_note)


class StockTransferLine(models.Model):
    transfer = models.ForeignKey(StockTransfer, on_delete=models.PROTECT, related_name="lines")
    product = models.ForeignKey("catalog.Product", on_delete=models.PROTECT, related_name="+")
    condition = models.CharField(max_length=10, choices=Condition.choices,
                                 default=Condition.NEW)  # e.g. a damaged piece sent for repair
    qty_sent = models.PositiveIntegerField()
    qty_received = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(qty_sent__gt=0), name="transfer_qty_positive"),
            models.CheckConstraint(
                condition=Q(qty_received__isnull=True) | Q(qty_received__lte=F("qty_sent")),
                name="transfer_received_within_sent"),
        ]
