from django.conf import settings
from django.db import models
from django.utils import timezone


class OutboxStatus(models.TextChoices):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class NotificationOutbox(models.Model):
    """A Telegram message to one person, written in the same transaction as the change it
    reports (so a rolled-back change never notifies). Sent by send_pending_notifications."""

    event_type = models.CharField(max_length=50, db_index=True)
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="notifications")
    chat_id = models.BigIntegerField()
    # {"text": str (Telegram HTML), "buttons": [[{"text", "callback_data"|"url"}]],
    #  "document": {"filename", "content_b64"}?}
    payload = models.JSONField()
    status = models.CharField(max_length=10, choices=OutboxStatus.choices,
                              default=OutboxStatus.PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.event_type} → {self.target_user_id} ({self.status})"


class AlertLog(models.Model):
    """Remembers that an alert went out, so it is sent at most once per key per day."""

    key = models.CharField(max_length=100)
    day = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "day"], name="one_alert_per_day")]
