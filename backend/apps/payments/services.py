"""Payments: recorded separately from sales (D2), always naming an Organization or Personal
account (D3). Never edited or deleted — rejected, reversed or corrected (D6)."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import ERPPermission, Role
from apps.audit.services import audit_log
from apps.core.exceptions import BusinessRuleError
from apps.core.numbering import PAYMENT, next_number
from apps.notifications.services import notify
from apps.sales.models import (
    BILLABLE_STATUSES,
    CLOSED_STATUSES,
    OrderPaymentStatus,
    ReceiptType,
    SalesOrder,
)

from . import selectors
from .models import (
    VALID_PAYMENT_STATUSES,
    AccountKind,
    Payment,
    PaymentAllocation,
    PaymentStatus,
)

CENT = Decimal("0.01")
_UNSET = object()


def money(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BusinessRuleError("invalid_amount", f"{value!r} is not an amount.") from exc
    if amount <= 0:
        raise BusinessRuleError("invalid_amount", "Amount must be greater than zero.")
    return amount


def _require(user, permission: str, action: str):
    if not user.has_erp_permission(permission):
        raise BusinessRuleError("permission_denied", f"You are not allowed to {action}.")


# ---------------------------------------------------------------- order status

def refresh_payment_status(order) -> SalesOrder:
    """unpaid / partial / paid from the order's active allocations."""
    paid = selectors.order_paid(order)
    if order.total_amount <= paid:
        status = OrderPaymentStatus.PAID
    elif paid > 0:
        status = OrderPaymentStatus.PARTIAL
    else:
        status = OrderPaymentStatus.UNPAID
    if order.payment_status != status:
        order.payment_status = status
        order.save(update_fields=["payment_status", "updated_at"])
    return order


def _deactivate(allocations, reason: str) -> set:
    """Deactivate allocations; returns the ids of the orders they touched."""
    orders = set()
    for allocation in allocations:
        allocation.is_active = False
        allocation.deactivated_at = timezone.now()
        allocation.deactivated_reason = reason[:255]
        allocation.save(update_fields=["is_active", "deactivated_at", "deactivated_reason"])
        orders.add(allocation.order_id)
    return orders


def _refresh_orders(order_ids):
    for order in SalesOrder.objects.filter(pk__in=order_ids):
        refresh_payment_status(order)


@transaction.atomic
def release_order_allocations(*, order, reason: str) -> None:
    """A cancelled or voided order gives its payments back as the customer's advance."""
    _deactivate(PaymentAllocation.objects.select_for_update().filter(order=order,
                                                                     is_active=True), reason)
    refresh_payment_status(order)


@transaction.atomic
def shrink_order_allocations(*, order, excess: Decimal, user, reason: str) -> None:
    """After a return lowers an order's total below what was paid, free `excess` from its
    newest allocations; that money becomes the customer's advance."""
    for allocation in (PaymentAllocation.objects.select_for_update()
                       .filter(order=order, is_active=True).order_by("-created_at", "-id")):
        if excess <= 0:
            break
        _deactivate([allocation], reason)
        keep = allocation.amount - excess
        if keep > 0:
            PaymentAllocation.objects.create(payment=allocation.payment, order=order,
                                             order_line=allocation.order_line, amount=keep,
                                             created_by=user)
        excess -= min(excess, allocation.amount)
    refresh_payment_status(order)


# ---------------------------------------------------------------- allocation

def _allocate(*, payment, order, amount, user, line=None) -> PaymentAllocation:
    amount = money(amount)
    order = SalesOrder.objects.select_for_update().get(pk=order.pk)
    if order.customer_id != payment.customer_id:
        raise BusinessRuleError("wrong_customer",
                                f"{order.number} belongs to another customer.")
    if order.fulfillment_status in CLOSED_STATUSES:
        raise BusinessRuleError("order_not_payable",
                                f"{order.number} is {order.fulfillment_status}.")
    if user.role == Role.SALESPERSON and order.salesperson_id != user.pk:
        raise BusinessRuleError("permission_denied",
                                "You can only take payments for your own sales.")
    if order.receipt_type == ReceiptType.OFFICIAL:
        if payment.account.kind != AccountKind.ORGANIZATION:
            raise BusinessRuleError(
                "official_needs_organization",
                "Official-receipt sales are paid only into an Organization account.")
        if not payment.receipt_number:
            raise BusinessRuleError("receipt_required",
                                    "Official-receipt sales need a receipt number.")
    if line is not None:
        if line.order_id != order.pk:
            raise BusinessRuleError("unknown_line", f"That line is not on {order.number}.")
        remaining = selectors.line_remaining(line)
        if amount > remaining:
            raise BusinessRuleError("over_line_balance",
                                    f"{line.product.code}: remaining is {remaining}.")
    remaining = selectors.order_remaining(order)
    if amount > remaining:
        raise BusinessRuleError("over_order_balance",
                                f"{order.number}: remaining is {remaining}.")
    if amount > selectors.payment_unallocated(payment):
        raise BusinessRuleError("over_allocated",
                                f"Only {selectors.payment_unallocated(payment)} of "
                                f"{payment.number} is left to allocate.")
    allocation = PaymentAllocation.objects.create(payment=payment, order=order,
                                                  order_line=line, amount=amount,
                                                  created_by=user)
    refresh_payment_status(order)
    return allocation


def _check_allocation_total(amount: Decimal, allocations):
    total = sum((money(a["amount"]) for a in allocations), Decimal("0"))
    if total > amount:
        raise BusinessRuleError("over_allocated", "Allocations exceed the payment amount.")


# ---------------------------------------------------------------- recording

def _check_receipt(account, receipt_number, exclude_pk=None):
    if account.kind == AccountKind.PERSONAL and receipt_number:
        raise BusinessRuleError("receipt_on_personal",
                                "Personal-account payments do not carry a receipt number.")
    if receipt_number:
        used = Payment.objects.filter(receipt_number=receipt_number,
                                      status__in=VALID_PAYMENT_STATUSES)
        if exclude_pk:
            used = used.exclude(pk=exclude_pk)
        if used.exists():
            raise BusinessRuleError("receipt_used",
                                    f"Receipt {receipt_number} is already on "
                                    f"{used.first().number}.")


@transaction.atomic
def record_payment(*, customer, account, amount, method, recorded_by, paid_at=None,
                   receipt_number=None, allocations=(), note="", replaces=None) -> Payment:
    """allocations = [{"order": SalesOrder, "line": SalesOrderLine | None, "amount": …}].
    Money not allocated stays the customer's advance until the accountant allocates it."""
    amount = money(amount)
    receipt_number = (receipt_number or "").strip() or None
    if not account.is_active:
        raise BusinessRuleError("inactive_account", "This payment account is closed.")
    if (recorded_by.role == Role.SALESPERSON
            and not recorded_by.allowed_payment_accounts.filter(pk=account.pk).exists()):
        raise BusinessRuleError("account_not_allowed", "You cannot record to this account.")
    if recorded_by.role == Role.STOREKEEPER:
        raise BusinessRuleError("permission_denied", "Storekeepers do not record payments.")
    _check_receipt(account, receipt_number)
    _check_allocation_total(amount, allocations)

    verified = recorded_by.has_erp_permission(ERPPermission.VERIFY_PAYMENTS)
    payment = Payment.objects.create(
        number=next_number(PAYMENT), customer=customer, account=account, amount=amount,
        method=method, receipt_number=receipt_number, paid_at=paid_at or timezone.now(),
        recorded_by=recorded_by, created_by=recorded_by, note=note, replaces=replaces,
        status=PaymentStatus.VERIFIED if verified else PaymentStatus.UNVERIFIED,
        verified_by=recorded_by if verified else None,
        verified_at=timezone.now() if verified else None)
    for a in allocations:
        _allocate(payment=payment, order=a["order"], line=a.get("line"), amount=a["amount"],
                  user=recorded_by)

    audit_log(actor=recorded_by, action="payment_recorded", obj=payment,
              after={"amount": str(amount), "account": account.name, "kind": account.kind,
                     "receipt_number": receipt_number,
                     "allocations": {a["order"].number: str(money(a["amount"]))
                                     for a in allocations}})
    if payment.status == PaymentStatus.UNVERIFIED:
        notify("payment.to_verify", payment)
    return payment


def _lock_payment(payment) -> Payment:
    return Payment.objects.select_for_update(of=("self",)).select_related(
        "account", "customer").get(pk=payment.pk)


@transaction.atomic
def allocate_payment(*, payment, allocations, user) -> Payment:
    """Allocate a payment's unallocated money (the advance) to orders or lines."""
    if user.role not in (Role.ACCOUNTANT, Role.ADMIN):
        raise BusinessRuleError("permission_denied", "Only the accountant allocates advances.")
    payment = _lock_payment(payment)
    if payment.status not in VALID_PAYMENT_STATUSES:
        raise BusinessRuleError("invalid_state", f"{payment.number} is {payment.status}.")
    if not allocations:
        raise BusinessRuleError("no_lines", "Choose at least one sale to allocate to.")
    _check_allocation_total(selectors.payment_unallocated(payment), allocations)
    for a in allocations:
        _allocate(payment=payment, order=a["order"], line=a.get("line"), amount=a["amount"],
                  user=user)
    audit_log(actor=user, action="payment_allocated", obj=payment,
              after={a["order"].number: str(money(a["amount"])) for a in allocations})
    return payment


@transaction.atomic
def allocate_oldest_first(*, payment, user) -> Payment:
    """Spread the payment's unallocated money over the customer's open sales, oldest first.
    Never automatic (Q20): the accountant presses it."""
    if user.role not in (Role.ACCOUNTANT, Role.ADMIN):
        raise BusinessRuleError("permission_denied", "Only the accountant allocates advances.")
    payment = _lock_payment(payment)
    if payment.status not in VALID_PAYMENT_STATUSES:
        raise BusinessRuleError("invalid_state", f"{payment.number} is {payment.status}.")
    left = selectors.payment_unallocated(payment)
    allocated = {}
    orders = (SalesOrder.objects.filter(customer=payment.customer,
                                        fulfillment_status__in=BILLABLE_STATUSES)
              .exclude(payment_status=OrderPaymentStatus.PAID)
              .order_by("confirmed_at", "id"))
    for order in orders:
        if left <= 0:
            break
        if order.receipt_type == ReceiptType.OFFICIAL and (
                payment.account.kind != AccountKind.ORGANIZATION or not payment.receipt_number):
            continue  # this payment cannot pay an official-receipt sale
        share = min(left, selectors.order_remaining(order))
        if share > 0:
            _allocate(payment=payment, order=order, amount=share, user=user)
            allocated[order.number] = str(share)
            left -= share
    if not allocated:
        raise BusinessRuleError("nothing_to_allocate", "No open sale this payment can pay.")
    audit_log(actor=user, action="payment_allocated", obj=payment, after=allocated)
    return payment


# ---------------------------------------------------------------- verify / reject / reverse

@transaction.atomic
def verify_payment(*, payment, user) -> Payment:
    _require(user, ERPPermission.VERIFY_PAYMENTS, "verify payments")
    payment = _lock_payment(payment)
    if payment.status != PaymentStatus.UNVERIFIED:
        raise BusinessRuleError("invalid_state", f"{payment.number} is {payment.status}.")
    payment.status = PaymentStatus.VERIFIED
    payment.verified_by, payment.verified_at = user, timezone.now()
    payment.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    audit_log(actor=user, action="payment_verified", obj=payment)
    return payment


def _close(payment, user, reason: str, status: str, action: str) -> Payment:
    reason = (reason or "").strip()
    if not reason:
        raise BusinessRuleError("reason_required", "Give a reason.")
    orders = _deactivate(payment.allocations.select_for_update().filter(is_active=True),
                         f"{action}: {reason}")
    payment.status = status
    payment.closed_by, payment.closed_at, payment.close_reason = user, timezone.now(), reason
    payment.save(update_fields=["status", "closed_by", "closed_at", "close_reason",
                                "updated_at"])
    _refresh_orders(orders)
    audit_log(actor=user, action=action, obj=payment, reason=reason,
              after={"status": status, "amount": str(payment.amount)})
    return payment


@transaction.atomic
def reject_payment(*, payment, user, reason: str) -> Payment:
    """The money never arrived (e.g. not on the bank statement)."""
    _require(user, ERPPermission.VERIFY_PAYMENTS, "reject payments")
    payment = _lock_payment(payment)
    if payment.status != PaymentStatus.UNVERIFIED:
        raise BusinessRuleError("invalid_state", f"{payment.number} is {payment.status}.")
    payment = _close(payment, user, reason, PaymentStatus.REJECTED, "payment_rejected")
    notify("payment.rejected", payment)
    return payment


@transaction.atomic
def reverse_payment(*, payment, user, reason: str) -> Payment:
    _require(user, ERPPermission.CORRECT_PAYMENTS, "reverse payments")
    payment = _lock_payment(payment)
    if payment.status not in VALID_PAYMENT_STATUSES:
        raise BusinessRuleError("invalid_state", f"{payment.number} is {payment.status}.")
    return _close(payment, user, reason, PaymentStatus.REVERSED, "payment_reversed")


@transaction.atomic
def correct_payment(*, payment, user, reason: str, amount=None, account=None, method=None,
                    paid_at=None, receipt_number=_UNSET, note=None,
                    allocations=None) -> Payment:
    """Reverse a wrong payment and record the corrected one, linked by `replaces` (D6).

    Without `allocations`, the old payment's active allocations are carried over, oldest
    first, up to the new amount; anything beyond it stays the customer's advance.
    """
    _require(user, ERPPermission.CORRECT_PAYMENTS, "correct payments")
    old = _lock_payment(payment)
    if old.status not in VALID_PAYMENT_STATUSES:
        raise BusinessRuleError("invalid_state", f"{old.number} is {old.status}.")
    carried = [{"order": a.order, "line": a.order_line, "amount": a.amount}
               for a in old.allocations.filter(is_active=True).select_related("order",
                                                                              "order_line")]
    _close(old, user, reason, PaymentStatus.REVERSED, "payment_reversed")
    new_amount = money(amount) if amount is not None else old.amount
    if allocations is None:
        allocations, room = [], new_amount
        for a in carried:
            if room <= 0:
                break
            allocations.append({**a, "amount": min(a["amount"], room)})
            room -= allocations[-1]["amount"]
    new = record_payment(
        customer=old.customer, account=account or old.account,
        amount=new_amount, method=method or old.method,
        paid_at=paid_at or old.paid_at, recorded_by=user,
        receipt_number=old.receipt_number if receipt_number is _UNSET else receipt_number,
        note=old.note if note is None else note,
        allocations=allocations, replaces=old)
    audit_log(actor=user, action="payment_corrected", obj=new, reason=reason,
              after={"replaces": old.number})
    return new
