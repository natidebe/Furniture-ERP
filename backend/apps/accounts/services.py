import secrets

from django.db import transaction

from apps.audit.services import audit_log

from .models import TelegramLinkToken, User

# No 0/O or 1/I, so codes are easy to type from a screen.
_LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_AUDITED_USER_FIELDS = ("role", "home_location_id", "is_active")


def _audited_fields(user: User) -> dict:
    return {field: getattr(user, field) for field in _AUDITED_USER_FIELDS}


@transaction.atomic
def create_user(*, actor, password: str, **fields) -> User:
    user = User(**fields)
    user.set_password(password)
    user.save()
    audit_log(actor=actor, action="user_created", obj=user, after=_audited_fields(user))
    return user


@transaction.atomic
def update_user(*, actor, user: User, password: str | None = None, **fields) -> User:
    user = User.objects.select_for_update().get(pk=user.pk)
    before = _audited_fields(user)
    for name, value in fields.items():
        setattr(user, name, value)
    if password:
        user.set_password(password)
    user.save()
    after = _audited_fields(user)
    if before != after or password:
        changed = {k: v for k, v in after.items() if before[k] != v}
        if password:
            changed["password"] = "changed"
        audit_log(actor=actor, action="user_updated", obj=user,
                  before={k: before[k] for k in changed if k in before}, after=changed)
    return user


@transaction.atomic
def create_link_code(*, user: User) -> TelegramLinkToken:
    """Issue a fresh one-time code for linking Telegram; earlier unused codes stop working."""
    TelegramLinkToken.objects.filter(user=user, used_at__isnull=True).delete()
    while True:
        token = "".join(secrets.choice(_LINK_ALPHABET) for _ in range(8))
        if not TelegramLinkToken.objects.filter(token=token).exists():
            return TelegramLinkToken.objects.create(user=user, token=token)
