"""Bot settings, from the environment (BUILD_PHASES.md Appendix B)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    bot_token: str
    service_token: str
    api_base_url: str
    web_app_url: str
    webhook_url: str
    webhook_secret: str
    redis_url: str
    port: int


def load() -> Config:
    return Config(
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        service_token=os.environ.get("BOT_SERVICE_TOKEN", ""),
        api_base_url=os.environ.get("API_BASE_URL", "http://api:8000/api/v1").rstrip("/"),
        web_app_url=os.environ.get("WEB_APP_URL", ""),
        # Empty: long polling (development). Set: webhook mode (production).
        webhook_url=os.environ.get("TELEGRAM_WEBHOOK_URL", ""),
        webhook_secret=os.environ.get("TELEGRAM_WEBHOOK_SECRET", ""),
        redis_url=os.environ.get("REDIS_URL", ""),
        port=int(os.environ.get("BOT_PORT", "8081")),
    )
