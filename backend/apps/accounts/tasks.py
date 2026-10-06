from datetime import timedelta

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .models import TelegramLinkToken


@shared_task
def expire_link_tokens() -> int:
    """Hourly: delete link codes that expired, and used ones older than a day."""
    now = timezone.now()
    deleted, _ = TelegramLinkToken.objects.filter(
        Q(used_at__isnull=True, expires_at__lt=now)
        | Q(used_at__lt=now - timedelta(days=1))).delete()
    return deleted
