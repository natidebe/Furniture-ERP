from .middleware import get_request_context
from .models import AuditLog, AuditSource


def audit_log(*, actor, action: str, obj, before=None, after=None, reason: str = "",
              source: str | None = None) -> AuditLog:
    """Record an important change. Call it inside the same transaction as the change.

    `source` and the IP come from the current request; outside a request the source
    is `system` unless given.
    """
    context = get_request_context()
    if source is None:
        source = context.source if context else AuditSource.SYSTEM
    return AuditLog.objects.create(
        actor=actor if actor is not None and actor.is_authenticated else None,
        action=action,
        model=obj._meta.label,
        object_id=str(obj.pk),
        before=before,
        after=after,
        reason=reason,
        source=source,
        ip=context.ip if context else None,
    )
