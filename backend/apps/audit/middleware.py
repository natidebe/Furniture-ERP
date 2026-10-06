from contextvars import ContextVar
from dataclasses import dataclass

from .models import AuditSource


@dataclass(frozen=True)
class RequestContext:
    ip: str | None
    source: str


_request_context: ContextVar[RequestContext | None] = ContextVar("audit_request_context",
                                                                default=None)


def get_request_context() -> RequestContext | None:
    """The current request's IP and source, or None outside a request (Celery, commands)."""
    return _request_context.get()


def _client_ip(request) -> str | None:
    # Behind nginx in production the client IP is the first X-Forwarded-For entry.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


class AuditContextMiddleware:
    """Stores the request IP and source (`X-Client: bot` → bot) for audit_log()."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        is_bot = request.headers.get("X-Client", "").lower() == "bot"
        context = RequestContext(
            ip=_client_ip(request),
            source=AuditSource.BOT if is_bot else AuditSource.WEB,
        )
        token = _request_context.set(context)
        try:
            return self.get_response(request)
        finally:
            _request_context.reset(token)
