def notify(event_type: str, obj, **context) -> None:
    """Queue a notification about `obj`. Call it inside the business transaction.

    Stub until Phase 4, which writes NotificationOutbox rows in the caller's transaction
    and picks the recipients per event type (see BUILD_PHASES.md 4.1).
    """
    return None
