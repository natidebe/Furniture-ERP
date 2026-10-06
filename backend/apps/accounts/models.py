from datetime import timedelta

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

LINK_TOKEN_LIFETIME = timedelta(minutes=10)


class Role(models.TextChoices):
    SALESPERSON = "salesperson"
    STOREKEEPER = "storekeeper"
    ACCOUNTANT = "accountant"
    ADMIN = "admin"


class ERPPermission(models.TextChoices):
    """Grantable per user by an admin. Admins always have all of them."""

    VIEW_PERSONAL_PAYMENTS = "view_personal_payments", "See Personal-account payments and totals"
    VERIFY_PAYMENTS = "verify_payments", "Verify or reject recorded payments"
    CORRECT_PAYMENTS = "correct_payments", "Reverse and re-record payments"
    CORRECT_TRANSACTIONS = "correct_transactions", "Void or correct sales and stock movements"
    APPROVE_ADJUSTMENTS = "approve_adjustments", "Approve stock adjustments"
    APPROVE_CREDIT = "approve_credit", "Confirm sales beyond a customer's credit rules"
    APPROVE_DISCOUNTS = "approve_discounts", "Give discounts above the salesperson limit"
    EXPORT_REPORTS = "export_reports", "Export reports to Excel"


# Applied when a user is created or their role changes; the admin can then add or remove.
# Accountants correct sales/stock only "when authorized", so that one is granted per user.
# Every staff member sees Personal-account payments (owner's answer to Q9).
ROLE_DEFAULT_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "salesperson": (ERPPermission.VIEW_PERSONAL_PAYMENTS,),
    "storekeeper": (ERPPermission.VIEW_PERSONAL_PAYMENTS,),
    "accountant": (
        ERPPermission.VIEW_PERSONAL_PAYMENTS,
        ERPPermission.VERIFY_PAYMENTS,
        ERPPermission.CORRECT_PAYMENTS,
        ERPPermission.APPROVE_ADJUSTMENTS,
        ERPPermission.APPROVE_CREDIT,
        ERPPermission.APPROVE_DISCOUNTS,
        ERPPermission.EXPORT_REPORTS,
    ),
    "admin": tuple(ERPPermission.values),
}


class ERPUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    full_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SALESPERSON)
    home_location = models.ForeignKey("locations.Location", null=True, blank=True,
                                      on_delete=models.PROTECT, related_name="staff")
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    # Accounts a salesperson may record payments to (others may use any account).
    allowed_payment_accounts = models.ManyToManyField("payments.PaymentAccount", blank=True,
                                                      related_name="allowed_users")

    history = HistoricalRecords()
    objects = ERPUserManager()

    class Meta:
        permissions = [(p.value, p.label) for p in ERPPermission]

    def __str__(self):
        return self.full_name or self.username

    @property
    def erp_permissions(self) -> list[str]:
        """ERP permissions granted to this user directly (not counting the admin role)."""
        return sorted(self.user_permissions.filter(
            content_type__app_label="accounts", codename__in=ERPPermission.values,
        ).values_list("codename", flat=True))

    def effective_erp_permissions(self) -> list[str]:
        if self.role == Role.ADMIN or self.is_superuser:
            return sorted(ERPPermission.values)
        return self.erp_permissions

    def has_erp_permission(self, permission: str) -> bool:
        if not (self.is_active and self.is_authenticated):
            return False
        return self.role == Role.ADMIN or self.has_perm(f"accounts.{permission}")

    def save(self, *args, **kwargs):
        if not self.full_name:
            self.full_name = self.get_full_name() or self.username
        super().save(*args, **kwargs)


def _default_link_expiry():
    return timezone.now() + LINK_TOKEN_LIFETIME


class TelegramLinkToken(models.Model):
    """One-time code a user sends to the bot (/start <code>) to link their Telegram account."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="telegram_link_tokens")
    token = models.CharField(max_length=8, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=_default_link_expiry)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.token} → {self.user}"

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()
