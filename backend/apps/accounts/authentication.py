"""How the Telegram bot calls the API: `Authorization: Bot <BOT_SERVICE_TOKEN>` plus
`X-Telegram-User: <telegram id>`. The request then runs as the linked user, with exactly that
user's permissions — the bot has none of its own."""

from django.conf import settings
from django.utils.crypto import constant_time_compare
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import User

KEYWORD = b"bot"


def is_bot_service(request) -> bool:
    """True when the request carries the bot's service token."""
    parts = get_authorization_header(request).split()
    expected = settings.BOT_SERVICE_TOKEN
    return (len(parts) == 2 and parts[0].lower() == KEYWORD and bool(expected)
            and constant_time_compare(parts[1].decode(errors="ignore"), expected))


class BotUserAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if not parts or parts[0].lower() != KEYWORD:
            return None  # not a bot call; let JWT try
        if not is_bot_service(request):
            raise AuthenticationFailed("Invalid bot service token.")
        telegram_id = request.headers.get("X-Telegram-User", "")
        if not telegram_id.isdigit():
            raise AuthenticationFailed("Missing Telegram user.")
        user = User.objects.filter(telegram_id=int(telegram_id), is_active=True).first()
        if user is None:
            raise AuthenticationFailed({"code": "not_linked",
                                        "detail": "This Telegram account is not linked."})
        return user, None

    def authenticate_header(self, request):
        return "Bot"
