import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Scheduled jobs (BUILD_PHASES.md 4.4); times are Africa/Addis_Ababa (CELERY_TIMEZONE).
app.conf.beat_schedule = {
    "send-pending-notifications": {
        "task": "apps.notifications.tasks.send_pending_notifications",
        "schedule": 15.0,
    },
    "daily-report": {
        "task": "apps.reports.tasks.daily_report",
        "schedule": crontab(hour=20, minute=0),
    },
    "weekly-report": {
        "task": "apps.reports.tasks.weekly_report",
        "schedule": crontab(hour=20, minute=0, day_of_week="sat"),
    },
    "monthly-report": {
        "task": "apps.reports.tasks.monthly_report",
        "schedule": crontab(hour=8, minute=0, day_of_month=1),
    },
    "yearly-report": {
        "task": "apps.reports.tasks.yearly_report",
        "schedule": crontab(hour=8, minute=0, day_of_month=1, month_of_year=1),
    },
    "nightly-stock-check": {
        "task": "apps.inventory.tasks.nightly_stock_check",
        "schedule": crontab(hour=2, minute=0),
    },
    "expire-link-tokens": {
        "task": "apps.accounts.tasks.expire_link_tokens",
        "schedule": crontab(minute=5),
    },
}
