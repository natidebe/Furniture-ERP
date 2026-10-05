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
    # allowed_payment_accounts (M2M → payments.PaymentAccount) is added in Phase 3.

    history = HistoricalRecords()
    objects = ERPUserManager()

    def __str__(self):
        return self.full_name or self.username

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
