from decimal import Decimal

from django.conf import settings as django_settings
from django.db import transaction

from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError

from .models import SystemSettings


def get_settings() -> SystemSettings:
    """The single settings row, created on first use from the environment's starting values."""
    obj = SystemSettings.objects.first()
    if obj is None:
        obj, _ = SystemSettings.objects.get_or_create(
            pk=1, defaults={"max_salesperson_discount_pct": Decimal(
                str(django_settings.MAX_SALESPERSON_DISCOUNT_PCT))})
    return obj


@transaction.atomic
def update_settings(*, user, **fields) -> SystemSettings:
    if user.role != "admin":
        raise BusinessRuleError("permission_denied", "Only the admin changes settings.")
    obj = get_settings()
    obj = SystemSettings.objects.select_for_update().get(pk=obj.pk)
    pct = fields.get("max_salesperson_discount_pct")
    if pct is not None and not 0 <= pct <= 100:
        raise BusinessRuleError("invalid_setting", "The discount limit is between 0 and 100%.")
    before = {k: str(getattr(obj, k)) for k in fields}
    for name, value in fields.items():
        setattr(obj, name, value)
    obj.updated_by = user
    obj.save()
    audit_log(actor=user, action="settings_changed", obj=obj, before=before,
              after={k: str(getattr(obj, k)) for k in fields})
    return obj
