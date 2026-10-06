from django.conf import settings
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from apps.core.models import ActiveModel, TimeStampedModel


class AccountKind(models.TextChoices):
    ORGANIZATION = "organization"
    PERSONAL = "personal"


class PaymentMethod(models.TextChoices):
    BANK = "bank"
    CASH = "cash"
    MOBILE_MONEY = "mobile_money"


class PaymentAccount(ActiveModel):
    """Where money is received. Every payment names one (D3)."""

    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=15, choices=AccountKind.choices)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices)
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    owner_name = models.CharField(max_length=100, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["kind", "name"]

    def __str__(self):
        return f"{self.name} ({self.kind})"


class PaymentStatus(models.TextChoices):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"
    REVERSED = "reversed"


# Payments that count as money received.
VALID_PAYMENT_STATUSES = (PaymentStatus.UNVERIFIED, PaymentStatus.VERIFIED)


class Payment(TimeStampedModel):
    """Money received from a customer. Never edited or deleted: wrong ones are rejected,
    reversed, or corrected (reversed + re-recorded with `replaces`)."""

    number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT,
                                 related_name="payments")
    account = models.ForeignKey(PaymentAccount, on_delete=models.PROTECT,
                                related_name="payments")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    method = models.CharField(max_length=15, choices=PaymentMethod.choices)
    receipt_number = models.CharField(max_length=50, null=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(db_index=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name="recorded_payments")
    status = models.CharField(max_length=12, choices=PaymentStatus.choices, db_index=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.PROTECT, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    # Set when rejected or reversed.
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.PROTECT, related_name="+")
    closed_at = models.DateTimeField(null=True, blank=True)
    close_reason = models.TextField(blank=True)
    replaces = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="replaced_by")
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-paid_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            # One receipt per payment (Q14): a receipt number is used by one valid payment.
            models.UniqueConstraint(
                fields=["receipt_number"],
                condition=Q(receipt_number__isnull=False) & Q(status__in=["unverified",
                                                                          "verified"]),
                name="receipt_number_used_once"),
        ]

    def __str__(self):
        return self.number

    @property
    def is_valid(self) -> bool:
        return self.status in VALID_PAYMENT_STATUSES


class PaymentAllocation(models.Model):
    """Ties part of a payment to an order (and optionally one of its lines).
    Deactivated, never deleted, when the payment or order no longer stands."""

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="allocations")
    order = models.ForeignKey("sales.SalesOrder", on_delete=models.PROTECT,
                              related_name="allocations")
    order_line = models.ForeignKey("sales.SalesOrderLine", null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    is_active = models.BooleanField(default=True, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    deactivated_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.CheckConstraint(condition=Q(amount__gt=0),
                                              name="allocation_amount_positive")]
