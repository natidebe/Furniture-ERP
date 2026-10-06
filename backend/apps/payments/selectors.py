"""Money read-outs. The balance rules (BUILD_PHASES.md 3.3):

- Order paid      = Σ active allocations to the order (unverified payments included).
- Order remaining = order total − order paid.
- Line paid       = Σ active allocations made to that line specifically.
- Payment unallocated = payment amount − Σ its active allocations (the customer's advance).
- Customer balance: see customers.selectors.customer_balance.
"""

from decimal import Decimal

from django.db.models import Q, Sum

from .models import VALID_PAYMENT_STATUSES, Payment, PaymentAllocation, PaymentStatus

ZERO = Decimal("0.00")


def _sum(qs, field="amount") -> Decimal:
    """Money always has two decimals, whatever the database returns."""
    return (qs.aggregate(t=Sum(field))["t"] or ZERO).quantize(ZERO)


def active_allocations():
    return PaymentAllocation.objects.filter(is_active=True,
                                            payment__status__in=VALID_PAYMENT_STATUSES)


def order_paid(order) -> Decimal:
    return _sum(active_allocations().filter(order=order))


def order_remaining(order) -> Decimal:
    return order.total_amount - order_paid(order)


def line_paid(line) -> Decimal:
    return _sum(active_allocations().filter(order_line=line))


def line_remaining(line) -> Decimal:
    return line.line_total - line_paid(line)


def payment_allocated(payment) -> Decimal:
    return _sum(payment.allocations.filter(is_active=True))


def payment_unallocated(payment) -> Decimal:
    if payment.status not in VALID_PAYMENT_STATUSES:
        return ZERO
    return payment.amount - payment_allocated(payment)


def can_see_amount(user, payment) -> bool:
    """Personal-account amounts need view_personal_payments (every role by default, D12);
    the person who recorded a payment always sees it."""
    if payment.account.kind != "personal":
        return True
    return payment.recorded_by_id == user.pk or user.has_erp_permission(
        "view_personal_payments")


def payments_for_user(user):
    """Salespeople see the payments they recorded or that pay their own orders;
    accountants and admins see all."""
    qs = Payment.objects.select_related("customer", "account", "recorded_by", "verified_by",
                                        "replaces")
    role = getattr(user, "role", None)
    if role in ("accountant", "admin"):
        return qs
    if role == "salesperson":
        return qs.filter(Q(recorded_by=user) | Q(allocations__order__salesperson=user)).distinct()
    return qs.none()


def unverified_payments():
    return Payment.objects.filter(status=PaymentStatus.UNVERIFIED)
