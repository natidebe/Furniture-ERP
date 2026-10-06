"""The client's own payment examples (userequirements.md) — the Phase 3 gate."""

from decimal import Decimal

import pytest

from apps.core.exceptions import BusinessRuleError
from apps.customers.selectors import customer_balance, customer_statement
from apps.payments import selectors as money
from apps.payments import services as payments
from apps.payments.models import Payment
from apps.sales import services as sales

D = Decimal


@pytest.fixture
def order_100k(staff, loc, goods, abc, stock):
    """5 cabinets × 20,000 = 100,000 ETB, sold from Piassa on credit to ABC Furniture."""
    stock(goods.cabinet, loc.PIA, 10)
    order = sales.create_order(customer=abc, branch=loc.PIA, user=staff.sales,
                               lines=[{"product": goods.cabinet, "qty": 5}])
    return sales.confirm_order(order=order, user=staff.sales)


def _pay(user, customer, account, amount, order=None, line=None, receipt=None):
    allocations = [{"order": order, "line": line, "amount": amount}] if order else []
    return payments.record_payment(customer=customer, account=account, amount=amount,
                                   method="bank", recorded_by=user, receipt_number=receipt,
                                   allocations=allocations)


@pytest.mark.django_db
def test_client_example_100k_partial_payments(order_100k, staff, accounts, abc):
    """Total 100,000; 40,000 Organization; 20,000 Personal → paid 60,000, remaining 40,000."""
    _pay(staff.accountant, abc, accounts.org, "40000", order_100k)
    _pay(staff.accountant, abc, accounts.personal, "20000", order_100k)

    order_100k.refresh_from_db()
    assert order_100k.total_amount == D("100000.00")
    assert money.order_paid(order_100k) == D("60000.00")
    assert money.order_remaining(order_100k) == D("40000.00")
    assert order_100k.payment_status == "partial"
    history = [(p.amount, p.account.kind) for p in Payment.objects.order_by("id")]
    assert history == [(D("40000.00"), "organization"), (D("20000.00"), "personal")]
    assert customer_balance(abc)["outstanding"] == D("40000.00")


@pytest.mark.django_db
def test_client_example_payment_for_specific_items(staff, loc, goods, abc, accounts, stock):
    """Chairs 50,000 + desks 40,000 + cabinet 20,000; pay 50,000 for the chairs only."""
    walk_in_priced = abc
    walk_in_priced.type = "walk_in"  # selling prices, as in the example
    walk_in_priced.save()
    for product, qty in ((goods.chair, 10), (goods.desk, 2), (goods.cabinet, 1)):
        stock(product, loc.PIA, qty)
    order = sales.create_order(customer=abc, branch=loc.PIA, user=staff.sales, lines=[
        {"product": goods.chair, "qty": 10}, {"product": goods.desk, "qty": 2},
        {"product": goods.cabinet, "qty": 1}])
    order = sales.confirm_order(order=order, user=staff.sales)
    chairs, desks, cabinet = order.lines.order_by("id")
    assert (chairs.line_total, desks.line_total, cabinet.line_total) == (
        D("50000"), D("40000"), D("20000"))

    _pay(staff.accountant, abc, accounts.org, "50000", order, line=chairs, receipt="R-1")

    assert money.line_remaining(chairs) == 0
    assert money.line_remaining(desks) == D("40000")
    assert money.line_remaining(cabinet) == D("20000")
    assert money.order_remaining(order) == D("60000")


@pytest.mark.django_db
def test_customer_credit_running_balance(order_100k, staff, accounts, abc):
    """ABC: purchases, payments and outstanding, with the statement agreeing."""
    _pay(staff.accountant, abc, accounts.org, "40000", order_100k)
    _pay(staff.accountant, abc, accounts.personal, "20000", order_100k)

    balance = customer_balance(abc)
    statement = customer_statement(abc, staff.accountant)

    assert (balance["total_purchases"], balance["total_paid"], balance["outstanding"]) == (
        D("100000.00"), D("60000.00"), D("40000.00"))
    assert statement["closing_balance"] == balance["outstanding"]
    assert [r.kind for r in statement["rows"]] == ["sale", "payment", "payment"]
    assert [r.account_kind for r in statement["rows"]][1:] == ["organization", "personal"]


@pytest.mark.django_db
def test_allocation_cannot_exceed_line_or_order(order_100k, staff, accounts, abc):
    line = order_100k.lines.get()
    with pytest.raises(BusinessRuleError) as exc:
        _pay(staff.accountant, abc, accounts.org, "100000.01", order_100k)
    assert exc.value.code == "over_order_balance"
    with pytest.raises(BusinessRuleError) as exc:
        _pay(staff.accountant, abc, accounts.org, "100001", order_100k, line=line)
    assert exc.value.code == "over_line_balance"
    assert not Payment.objects.exists()


@pytest.mark.django_db
def test_unallocated_money_is_an_advance_until_the_accountant_allocates(order_100k, staff,
                                                                         accounts, abc):
    payment = _pay(staff.accountant, abc, accounts.org, "30000")  # no sale chosen (Q20)
    assert money.payment_unallocated(payment) == D("30000")
    assert money.order_paid(order_100k) == 0
    assert customer_balance(abc)["unallocated"] == D("30000")

    payments.allocate_oldest_first(payment=payment, user=staff.accountant)

    assert money.order_paid(order_100k) == D("30000")
    assert money.payment_unallocated(payment) == 0


@pytest.mark.django_db
def test_over_allocating_a_payment_is_refused(order_100k, staff, accounts, abc):
    with pytest.raises(BusinessRuleError) as exc:
        payments.record_payment(customer=abc, account=accounts.org, amount="1000",
                                method="bank", recorded_by=staff.accountant,
                                allocations=[{"order": order_100k, "amount": "1500"}])
    assert exc.value.code == "over_allocated"


@pytest.mark.django_db
def test_salesperson_uses_only_allowed_accounts(order_100k, staff, accounts, abc):
    with pytest.raises(BusinessRuleError) as exc:
        _pay(staff.sales, abc, accounts.org, "1000", order_100k)
    assert exc.value.code == "account_not_allowed"

    staff.sales.allowed_payment_accounts.add(accounts.org)
    payment = _pay(staff.sales, abc, accounts.org, "1000", order_100k)
    assert payment.status == "unverified"  # the accountant verifies it


@pytest.mark.django_db
def test_salesperson_takes_payments_only_for_own_sales(order_100k, staff, accounts, abc,
                                                       make_user, loc):
    other = make_user(role="salesperson", home_location=loc.PIA)
    other.allowed_payment_accounts.add(accounts.org)
    with pytest.raises(BusinessRuleError) as exc:
        _pay(other, abc, accounts.org, "1000", order_100k)
    assert exc.value.code == "permission_denied"


@pytest.mark.django_db
def test_reversing_a_payment_restores_the_balance_and_keeps_the_row(order_100k, staff,
                                                                     accounts, abc):
    payment = _pay(staff.accountant, abc, accounts.org, "40000", order_100k)

    payments.reverse_payment(payment=payment, user=staff.accountant, reason="Bounced")

    payment.refresh_from_db()
    assert payment.status == "reversed"
    assert money.order_remaining(order_100k) == D("100000")
    order_100k.refresh_from_db()
    assert order_100k.payment_status == "unpaid"
    assert customer_balance(abc)["outstanding"] == D("100000")


@pytest.mark.django_db
def test_correcting_a_payment_links_old_and_new(order_100k, staff, accounts, abc):
    wrong = _pay(staff.accountant, abc, accounts.org, "40000", order_100k)

    fixed = payments.correct_payment(payment=wrong, user=staff.accountant,
                                     reason="Typed 40,000 instead of 4,000", amount="4000")

    wrong.refresh_from_db()
    assert wrong.status == "reversed"
    assert fixed.replaces == wrong
    assert money.order_paid(order_100k) == D("4000")


@pytest.mark.django_db
def test_verify_and_reject_need_the_permission(order_100k, staff, accounts, abc):
    from apps.accounts.services import set_erp_permissions

    staff.sales.allowed_payment_accounts.add(accounts.org)
    payment = _pay(staff.sales, abc, accounts.org, "1000", order_100k)
    set_erp_permissions(staff.accountant, [])

    with pytest.raises(BusinessRuleError):
        payments.verify_payment(payment=payment, user=staff.accountant)
    payments.verify_payment(payment=payment, user=staff.admin)
    payment.refresh_from_db()
    assert (payment.status, payment.verified_by) == ("verified", staff.admin)


@pytest.mark.django_db
def test_rejected_payment_no_longer_pays_the_order(order_100k, staff, accounts, abc):
    staff.sales.allowed_payment_accounts.add(accounts.org)
    payment = _pay(staff.sales, abc, accounts.org, "1000", order_100k)

    payments.reject_payment(payment=payment, user=staff.accountant, reason="Not in bank")

    assert money.order_paid(order_100k) == 0
