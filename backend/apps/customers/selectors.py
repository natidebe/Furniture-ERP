from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone

from apps.payments.models import VALID_PAYMENT_STATUSES, Payment
from apps.payments.selectors import ZERO, can_see_amount, payment_unallocated
from apps.sales.models import BILLABLE_STATUSES, SalesOrder, SalesReturn

from .models import Customer


def _sum(qs, field) -> Decimal:
    return (qs.aggregate(t=Sum(field))["t"] or ZERO).quantize(ZERO)


def _billable_orders(customer):
    return SalesOrder.objects.filter(customer=customer, fulfillment_status__in=BILLABLE_STATUSES)


def _valid_payments(customer):
    return Payment.objects.filter(customer=customer, status__in=VALID_PAYMENT_STATUSES)


def customer_balance(customer) -> dict:
    """The customer's credit position.

    - total_purchases: Σ totals of confirmed sales (not draft, cancelled or voided), after returns
    - total_paid: Σ payments that stand (unverified + verified)
    - outstanding: what they owe = total_purchases − total_paid, when positive
    - prepaid: paid beyond their purchases, when positive
    - unallocated: payment money not yet tied to a sale (the accountant allocates it, Q20)
    """
    purchases = _sum(_billable_orders(customer), "total_amount")
    paid = _sum(_valid_payments(customer), "amount")
    unallocated = sum((payment_unallocated(p) for p in _valid_payments(customer)), ZERO)
    balance = purchases - paid
    return {
        "total_purchases": purchases,
        "total_paid": paid,
        "outstanding": max(balance, ZERO),
        "prepaid": max(-balance, ZERO),
        "unallocated": unallocated,
    }


def customers_with_balance():
    return Customer.objects.all()


@dataclass
class StatementRow:
    date: datetime
    kind: str          # "sale", "return" or "payment"
    number: str
    description: str
    debit: Decimal | None
    credit: Decimal | None
    balance: Decimal
    account_kind: str | None = None
    hidden: bool = False  # a Personal payment the viewer may not see


def _start(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))


def customer_statement(customer, user, date_from: date | None = None,
                       date_to: date | None = None) -> dict:
    """Chronological rows — sales as debits, returns and payments as credits — with a running
    balance. The closing balance equals total_purchases − total_paid.

    Sales count from their confirmation, at the value they were confirmed at; returns lower it.
    """
    events = []
    for order in _billable_orders(customer).prefetch_related("lines", "returns"):
        gross = sum((line.line_total for line in order.lines.all()), ZERO)
        events.append((order.confirmed_at, "sale", order.number,
                       f"Sale at {order.branch.code}", gross, None, None, False))
    for ret in SalesReturn.objects.filter(order__customer=customer,
                                          order__fulfillment_status__in=BILLABLE_STATUSES):
        events.append((ret.created_at, "return", ret.number, f"Return on {ret.order.number}",
                       None, ret.amount, None, False))
    for payment in _valid_payments(customer).select_related("account"):
        hidden = not can_see_amount(user, payment)
        events.append((payment.paid_at, "payment", payment.number,
                       "Payment" + (f" (receipt {payment.receipt_number})"
                                    if payment.receipt_number else ""),
                       None, payment.amount, payment.account.kind, hidden))
    events.sort(key=lambda e: (e[0], e[2]))

    opening = ZERO
    rows = []
    balance = ZERO
    for when, kind, number, text, debit, credit, account_kind, hidden in events:
        balance += (debit or ZERO) - (credit or ZERO)
        if date_from and when < _start(date_from):
            opening = balance
            continue
        if date_to and when >= _start(date_to) + timedelta(days=1):
            continue
        rows.append(StatementRow(when, kind, number, text, debit,
                                 None if hidden else credit, balance, account_kind, hidden))
    return {"opening_balance": opening, "rows": rows,
            "closing_balance": rows[-1].balance if rows else opening}


def phone_used_by_others(phone: str, exclude_pk=None) -> list[Customer]:
    if not phone:
        return []
    qs = Customer.objects.filter(phone=phone)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return list(qs[:5])


def search_customers(q: str):
    return Customer.objects.filter(Q(name__icontains=q) | Q(phone__icontains=q)
                                   | Q(shop_name__icontains=q))
