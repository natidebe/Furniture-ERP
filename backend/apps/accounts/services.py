import secrets

from django.contrib.auth.models import Permission
from django.db import transaction
from django.utils import timezone

from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError

from .models import ROLE_DEFAULT_PERMISSIONS, ERPPermission, TelegramLinkToken, User

# No 0/O or 1/I, so codes are easy to type from a screen.
_LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_AUDITED_USER_FIELDS = ("role", "home_location_id", "is_active")


def _audited_fields(user: User) -> dict:
    data = {field: getattr(user, field) for field in _AUDITED_USER_FIELDS}
    if user.pk:
        data["payment_accounts"] = sorted(
            user.allowed_payment_accounts.values_list("name", flat=True))
    return data


def set_erp_permissions(user: User, permissions) -> None:
    """Replace the user's ERP permissions with exactly `permissions` (codenames)."""
    wanted = set(permissions)
    unknown = wanted - set(ERPPermission.values)
    if unknown:
        raise ValueError(f"Unknown permissions: {sorted(unknown)}")
    erp = Permission.objects.filter(content_type__app_label="accounts",
                                    codename__in=ERPPermission.values)
    user.user_permissions.remove(*erp.exclude(codename__in=wanted))
    user.user_permissions.add(*erp.filter(codename__in=wanted))
    # Django caches permissions on the instance.
    for cache in ("_perm_cache", "_user_perm_cache"):
        user.__dict__.pop(cache, None)


def apply_role_defaults(user: User) -> None:
    set_erp_permissions(user, ROLE_DEFAULT_PERMISSIONS.get(user.role, ()))


@transaction.atomic
def create_user(*, actor, password: str, permissions=None, allowed_payment_accounts=None,
                **fields) -> User:
    """Create a user. ERP permissions default to the role's; pass `permissions` to override."""
    user = User(**fields)
    user.set_password(password)
    user.save()  # the post_save signal applies the role defaults
    if permissions is not None:
        set_erp_permissions(user, permissions)
    if allowed_payment_accounts is not None:
        user.allowed_payment_accounts.set(allowed_payment_accounts)
    audit_log(actor=actor, action="user_created", obj=user,
              after={**_audited_fields(user), "permissions": user.erp_permissions})
    return user


@transaction.atomic
def update_user(*, actor, user: User, password: str | None = None, permissions=None,
                allowed_payment_accounts=None, **fields) -> User:
    """Update a user. A role change resets ERP permissions to the new role's defaults,
    unless `permissions` is also given."""
    user = User.objects.select_for_update().get(pk=user.pk)
    before = {**_audited_fields(user), "permissions": user.erp_permissions}
    for name, value in fields.items():
        setattr(user, name, value)
    if password:
        user.set_password(password)
    user.save()

    if permissions is not None:
        set_erp_permissions(user, permissions)
    elif before["role"] != user.role:
        apply_role_defaults(user)
    if allowed_payment_accounts is not None:
        user.allowed_payment_accounts.set(allowed_payment_accounts)

    after = {**_audited_fields(user), "permissions": user.erp_permissions}
    changed = {k: v for k, v in after.items() if before[k] != v}
    if password:
        changed["password"] = "changed"
    if changed:
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


@transaction.atomic
def link_telegram(*, code: str, telegram_id: int) -> User:
    """/start <code> in the bot: tie this Telegram account to the user who made the code."""
    token = (TelegramLinkToken.objects.select_for_update().select_related("user")
             .filter(token=(code or "").strip().upper()).first())
    if token is None or not token.is_valid or not token.user.is_active:
        raise BusinessRuleError("invalid_code",
                                "This code is wrong or expired. Get a new one in the web app.")
    taken = User.objects.filter(telegram_id=telegram_id).exclude(pk=token.user_id).first()
    if taken is not None:
        raise BusinessRuleError("telegram_in_use",
                                "This Telegram account is linked to another user; ask the "
                                "admin to unlink it first.")
    user = token.user
    before = user.telegram_id
    user.telegram_id = telegram_id
    user.save(update_fields=["telegram_id"])
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    audit_log(actor=user, action="telegram_linked", obj=user, source="bot",
              before={"telegram_id": before}, after={"telegram_id": telegram_id})
    return user


@transaction.atomic
def unlink_telegram(*, user: User, actor) -> User:
    if actor.pk != user.pk and actor.role != "admin":
        raise BusinessRuleError("permission_denied", "Only the admin unlinks someone else.")
    before = user.telegram_id
    user.telegram_id = None
    user.save(update_fields=["telegram_id"])
    audit_log(actor=actor, action="telegram_unlinked", obj=user,
              before={"telegram_id": before}, after={"telegram_id": None})
    return user
