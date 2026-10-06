import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import NotificationOutbox, OutboxStatus
from .telegram import TelegramError, send

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
BASE_DELAY = timedelta(seconds=15)


@shared_task
def send_pending_notifications(batch: int = 50) -> int:
    """Outbox → Telegram, every 15 seconds. Each row is locked while it is sent
    (skip_locked), so two workers never send the same message. A failure is retried with a
    growing delay (15 s, 30 s, 60 s, …); after 5 attempts, or a permanent error such as a
    user who blocked the bot, the row is marked failed."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return 0  # nothing can be sent; rows wait until the bot is configured
    sent = 0
    with transaction.atomic():
        rows = list(NotificationOutbox.objects.select_for_update(skip_locked=True)
                    .filter(status=OutboxStatus.PENDING, next_attempt_at__lte=timezone.now())
                    .order_by("id")[:batch])
        for row in rows:
            try:
                send(row.chat_id, row.payload)
            except TelegramError as exc:
                row.attempts += 1
                row.last_error = str(exc)[:1000]
                if exc.permanent or row.attempts >= MAX_ATTEMPTS:
                    row.status = OutboxStatus.FAILED
                else:
                    delay = (timedelta(seconds=exc.retry_after) if exc.retry_after
                             else BASE_DELAY * 2 ** (row.attempts - 1))
                    row.next_attempt_at = timezone.now() + delay
                logger.warning("Telegram send failed for outbox %s: %s", row.pk, exc)
            else:
                row.status = OutboxStatus.SENT
                row.sent_at = timezone.now()
                sent += 1
            row.save(update_fields=["status", "attempts", "last_error", "next_attempt_at",
                                    "sent_at"])
    return sent
