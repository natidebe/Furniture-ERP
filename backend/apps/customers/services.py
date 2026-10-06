from django.db import transaction

from apps.accounts.models import ERPPermission, Role
from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError

from .models import Customer

CREDIT_FIELDS = ("credit_allowed", "credit_limit")
_AUDITED = ("name", "phone", "shop_name", "city", "type", "credit_allowed", "credit_limit",
            "is_active")


def _snapshot(customer) -> dict:
    return {f: str(getattr(customer, f)) if getattr(customer, f) is not None else None
            for f in _AUDITED}


def _check_credit_rights(user, fields):
    if set(CREDIT_FIELDS) & set(fields) and not user.has_erp_permission(
            ERPPermission.APPROVE_CREDIT):
        raise BusinessRuleError("permission_denied", "Only the accountant sets credit terms.")


@transaction.atomic
def create_customer(*, user, **fields) -> Customer:
    if user.role == Role.STOREKEEPER:
        raise BusinessRuleError("permission_denied", "Storekeepers do not create customers.")
    _check_credit_rights(user, {k for k, v in fields.items() if k in CREDIT_FIELDS and v})
    customer = Customer.objects.create(created_by=user, **fields)
    audit_log(actor=user, action="customer_created", obj=customer, after=_snapshot(customer))
    return customer


@transaction.atomic
def update_customer(*, user, customer, **fields) -> Customer:
    if user.role == Role.STOREKEEPER:
        raise BusinessRuleError("permission_denied", "Storekeepers do not edit customers.")
    customer = Customer.objects.select_for_update().get(pk=customer.pk)
    changed_credit = {f for f in CREDIT_FIELDS
                      if f in fields and fields[f] != getattr(customer, f)}
    _check_credit_rights(user, changed_credit)
    before = _snapshot(customer)
    for name, value in fields.items():
        setattr(customer, name, value)
    customer.save()
    after = _snapshot(customer)
    changed = {k: v for k, v in after.items() if before[k] != v}
    if changed:
        audit_log(actor=user, action="customer_updated", obj=customer,
                  before={k: before[k] for k in changed}, after=changed)
    return customer
