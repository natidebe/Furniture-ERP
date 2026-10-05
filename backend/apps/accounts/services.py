import secrets

from django.contrib.auth.models import Permission
from django.db import transaction

from apps.audit.services import audit_log

from .models import ROLE_DEFAULT_PERMISSIONS, ERPPermission, TelegramLinkToken, User

# No 0/O or 1/I, so codes are easy to type from a screen.
_LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_AUDITED_USER_FIELDS = ("role", "home_location_id", "is_active")


def _audited_fields(user: User) -> dict:
    return {field: getattr(user, field) for field in _AUDITED_USER_FIELDS}


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
def create_user(*, actor, password: str, permissions=None, **fields) -> User:
    """Create a user. ERP permissions default to the role's; pass `permissions` to override."""
    user = User(**fields)
    user.set_password(password)
    user.save()  # the post_save signal applies the role defaults
    if permissions is not None:
        set_erp_permissions(user, permissions)
    audit_log(actor=actor, action="user_created", obj=user,
              after={**_audited_fields(user), "permissions": user.erp_permissions})
    return user


@transaction.atomic
def update_user(*, actor, user: User, password: str | None = None, permissions=None,
                **fields) -> User:
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
