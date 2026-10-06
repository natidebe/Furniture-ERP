"""Plain HTTPS calls to the Telegram Bot API, used by send_pending_notifications."""

import base64

import httpx
from django.conf import settings

API = "https://api.telegram.org/bot{token}/{method}"
MAX_TEXT = 4096


class TelegramError(Exception):
    def __init__(self, message: str, *, permanent: bool = False, retry_after: int | None = None):
        super().__init__(message)
        self.permanent = permanent  # retrying will not help (blocked bot, bad chat id, ...)
        self.retry_after = retry_after


def _call(client: httpx.Client, method: str, **kwargs) -> dict:
    url = API.format(token=settings.TELEGRAM_BOT_TOKEN, method=method)
    try:
        response = client.post(url, timeout=15, **kwargs)
    except httpx.HTTPError as exc:
        raise TelegramError(f"network: {exc}") from exc
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 200 and body.get("ok"):
        return body["result"]
    description = body.get("description") or response.text[:200]
    if response.status_code == 429:
        raise TelegramError(description, retry_after=body.get("parameters", {}).get(
            "retry_after"))
    # 400 bad request / 403 blocked by the user / 404: the same message will fail again.
    raise TelegramError(f"{response.status_code}: {description}",
                        permanent=response.status_code in (400, 403, 404))


def send(chat_id: int, payload: dict, *, client: httpx.Client | None = None) -> None:
    """Send one outbox payload: {"text", "buttons"?, "document"?}."""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise TelegramError("TELEGRAM_BOT_TOKEN is not set")
    own_client = client is None
    client = client or httpx.Client()
    try:
        message = {"chat_id": chat_id, "text": payload["text"][:MAX_TEXT], "parse_mode": "HTML",
                   "disable_web_page_preview": True}
        if payload.get("buttons"):
            message["reply_markup"] = {"inline_keyboard": payload["buttons"]}
        _call(client, "sendMessage", json=message)
        document = payload.get("document")
        if document:
            _call(client, "sendDocument", data={"chat_id": str(chat_id)},
                  files={"document": (document["filename"],
                                      base64.b64decode(document["content_b64"]))})
    finally:
        if own_client:
            client.close()
