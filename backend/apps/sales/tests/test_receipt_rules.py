"""Receipts and account kinds (D3, owner's answers to Q14)."""

import pytest

from apps.core.exceptions import BusinessRuleError
from apps.payments import services as payments
from apps.sales import services as sales


@pytest.fixture
def official_order(staff, loc, goods, abc, stock):
    stock(goods.desk, loc.PIA, 5)
    order = sales.create_order(customer=abc, branch=loc.PIA, user=staff.sales,
                               receipt_type="official",
                               lines=[{"product": goods.desk, "qty": 2}])
    return sales.confirm_order(order=order, user=staff.sales)


def _pay(user, account, order, amount="1000", receipt=None, customer=None):
    return payments.record_payment(customer=customer or order.customer, account=account,
                                   amount=amount, method="bank", recorded_by=user,
                                   receipt_number=receipt,
                                   allocations=[{"order": order, "amount": amount}])


@pytest.mark.django_db
def test_official_sale_needs_a_receipt_number(official_order, staff, accounts):
    with pytest.raises(BusinessRuleError) as exc:
        _pay(staff.accountant, accounts.org, official_order)
    assert exc.value.code == "receipt_required"


@pytest.mark.django_db
def test_official_sale_takes_only_organization_payments(official_order, staff, accounts):
    with pytest.raises(BusinessRuleError) as exc:
        _pay(staff.accountant, accounts.personal, official_order)
    assert exc.value.code == "official_needs_organization"


@pytest.mark.django_db
def test_one_receipt_per_payment(official_order, staff, accounts):
    _pay(staff.accountant, accounts.org, official_order, receipt="R-000981")
    with pytest.raises(BusinessRuleError) as exc:
        _pay(staff.accountant, accounts.org, official_order, receipt="R-000981")
    assert exc.value.code == "receipt_used"
    _pay(staff.accountant, accounts.org, official_order, receipt="R-000982")


@pytest.mark.django_db
def test_a_reversed_payments_receipt_can_be_used_by_its_correction(official_order, staff,
                                                                    accounts):
    first = _pay(staff.accountant, accounts.org, official_order, receipt="R-1")
    fixed = payments.correct_payment(payment=first, user=staff.accountant, reason="Amount",
                                     amount="900")
    assert fixed.receipt_number == "R-1"


@pytest.mark.django_db
def test_personal_payments_never_carry_a_receipt(staff, accounts, abc):
    with pytest.raises(BusinessRuleError) as exc:
        payments.record_payment(customer=abc, account=accounts.personal, amount="100",
                                method="cash", recorded_by=staff.accountant,
                                receipt_number="R-5")
    assert exc.value.code == "receipt_on_personal"


@pytest.mark.django_db
def test_no_receipt_sale_takes_both_kinds(staff, loc, goods, abc, accounts, stock):
    stock(goods.desk, loc.PIA, 5)
    order = sales.confirm_order(order=sales.create_order(
        customer=abc, branch=loc.PIA, user=staff.sales,
        lines=[{"product": goods.desk, "qty": 1}]), user=staff.sales)

    _pay(staff.accountant, accounts.org, order, "10000")
    _pay(staff.accountant, accounts.personal, order, "5000")
