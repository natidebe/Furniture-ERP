from django.conf import settings
from django.db import models


class AuditSource(models.TextChoices):
    WEB = "web"
    BOT = "bot"
    SYSTEM = "system"


class AuditLog(models.Model):
    """Who changed what, and why. Rows are only ever created, never edited."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=50)
    model = models.CharField(max_length=100)      # app label + model, e.g. "catalog.Product"
    object_id = models.CharField(max_length=40)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=AuditSource.choices,
                              default=AuditSource.SYSTEM)
    ip = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [models.Index(fields=["model", "object_id"])]

    def __str__(self):
        return f"{self.action} {self.model}#{self.object_id}"
