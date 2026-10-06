from decimal import Decimal

import pytest

from apps.accounts.models import ERPPermission
from apps.accounts.services import set_erp_permissions
from apps.catalog.services import change_price
from apps.core.exceptions import BusinessRuleError
from apps.customers.selectors import customer_balance
from apps.inventory.models import MovementType, StockMovement
from apps.inventory.selectors import balance_mismatches
from apps.inventory.services import receive_transfer
from apps.payments import selectors as money
from apps.payments import services as payments
from apps.requests import services as requests
from apps.sales import services as sales
from apps.sales.models import DeliveryNote

D = Decimal


def _order(staff, loc, customer, lines, user=None, **kwargs):
    return sales.create_order(customer=customer, branch=loc.PIA, user=user or staff.sales,
                              lines=lines, **kwargs)


def _pay_full(staff, accounts, order):
    return payments.record_payment(
        customer=order.customer, account=accounts.org, amount=order.total_amount,
        method="cash", recorded_by=staff.accountant,
        allocations=[{"order": order, "amount": order.total_amount}])


# ---------------------------------------------------------------- pricing

@pytest.mark.django_db
def test_prices_come_from_the_product_wholesale_for_resellers(staff, loc, goods, abc,
                                                              walk_in):
    reseller = _order(staff, loc, abc, [{"product": goods.chair, "qty": 2}])
    walk = _order(staff, loc, walk_in, [{"product": goods.chair, "qty": 2,
                                         "unit_price": D("1")}])  # ignored

    assert reseller.lines.get().unit_price == D("4500")
    assert walk.lines.get().unit_price == D("5000")
    assert walk.total_amount == D("10000")


@pytest.mark.django_db
def test_later_price_change_does_not_alter_the_order(staff, loc, goods, walk_in):
    order = _order(staff, loc, walk_in, [{"product": goods.desk, "qty": 1}])
    change_price(product=goods.desk, new_price=D("25000"), user=staff.admin)

    order.refresh_from_db()
    assert order.total_amount == D("20000")


@pytest.mark.django_db
def test_changing_the_customer_of_a_draft_reprices_it(staff, loc, goods, abc, walk_in):
    order = _order(staff, loc, walk_in, [{"product": goods.chair, "qty": 2}])

    order = sales.update_draft_order(order=order, user=staff.sales, customer=abc)

    assert order.lines.get().unit_price == D("4500")
    assert order.total_amount == D("9000")


@pytest.mark.django_db
def test_discount_above_the_limit_needs_approval(staff, loc, goods, walk_in):
    from apps.core.services import update_settings

    lines = [{"product": goods.desk, "qty": 1, "discount": D("1000")}]  # 5%
    with pytest.raises(BusinessRuleError) as exc:
        _order(staff, loc, walk_in, lines)
    assert exc.value.code == "discount_needs_approval"

    update_settings(user=staff.admin, max_salesperson_discount_pct=D("5"))
    order = _order(staff, loc, walk_in, lines)
    assert order.total_amount == D("19000")
    _order(staff, loc, walk_in, lines, user=staff.accountant)  # approve_discounts


@pytest.mark.django_db
def test_salesperson_sells_only_at_own_branch(staff, loc, goods, walk_in):
    with pytest.raises(BusinessRuleError) as exc:
        sales.create_order(customer=walk_in, branch=loc.DEN, user=staff.sales,
                           lines=[{"product": goods.desk, "qty": 1}])
    assert exc.value.code == "wrong_location"


# ---------------------------------------------------------------- walk-in at the branch

@pytest.mark.django_db
def test_walk_in_sale_paid_now_sells_from_branch_stock(staff, loc, goods, walk_in, accounts,
                                                       stock, balance):
    stock(goods.desk, loc.PIA, 3)
    staff.sales.allowed_payment_accounts.add(accounts.org)
    order = _order(staff, loc, walk_in, [{"product": goods.desk, "qty": 2}],
                   payment={"account": accounts.org, "amount": D("40000"), "method": "cash"})

    order = sales.confirm_order(order=order, user=staff.sales)

    assert order.fulfillment_status == "released"
    assert order.payment_status == "paid"
    assert balance(goods.desk, loc.PIA) == (1, 0)
    note = DeliveryNote.objects.get(order=order)
    assert note.location == loc.PIA
    movement = StockMovement.objects.get(type=MovementType.SALE)
    assert (movement.transaction_number, movement.reference_id, movement.customer) == (
        order.number, note.number, walk_in)


@pytest.mark.django_db
def test_walk_in_cannot_leave_unpaid_unless_accountant_approves(staff, loc, goods, walk_in,
                                                                stock):
    stock(goods.desk, loc.PIA, 3)
    order = _order(staff, loc, walk_in, [{"product": goods.desk, "qty": 1}])

    with pytest.raises(BusinessRuleError) as exc:
        sales.confirm_order(order=order, user=staff.sales)
    assert exc.value.code == "credit_not_allowed"

    sales.confirm_order(order=order, user=staff.accountant)  # approve_credit


@pytest.mark.django_db
def test_credit_limit(staff, loc, goods, abc, stock):
    stock(goods.desk, loc.PIA, 10)
    abc.credit_limit = D("30000")
    abc.save()
    sales.confirm_order(order=_order(staff, loc, abc, [{"product": goods.desk, "qty": 1}]),
                        user=staff.sales)  # owes 20,000

    second = _order(staff, loc, abc, [{"product": goods.desk, "qty": 1}])
    with pytest.raises(BusinessRuleError) as exc:
        sales.confirm_order(order=second, user=staff.sales)  # would owe 40,000
    assert exc.value.code == "credit_limit_exceeded"


@pytest.mark.django_db
def test_not_enough_branch_stock_stops_the_confirmation(staff, loc, goods, abc, stock,
                                                        balance):
    stock(goods.desk, loc.PIA, 1)
    order = _order(staff, loc, abc, [{"product": goods.desk, "qty": 2}])

    with pytest.raises(BusinessRuleError) as exc:
        sales.confirm_order(order=order, user=staff.sales)

    assert exc.value.code == "insufficient_stock"
    order.refresh_from_db()
    assert order.fulfillment_status == "draft"
    assert balance(goods.desk, loc.PIA) == (1, 0)


# ---------------------------------------------------------------- goods from Pawlos

@pytest.fixture
def pawlos_order(staff, loc, goods, abc, stock):
    stock(goods.chair, loc.PAW, 50)
    order = _order(staff, loc, abc, [{"product": goods.chair, "qty": 20,
                                      "source_location": loc.PAW}], channel="phone")
    return sales.confirm_order(order=order, user=staff.sales)


@pytest.mark.django_db
def test_pawlos_line_creates_a_request_under_the_sale_number(pawlos_order, loc, balance,
                                                             goods):
    request = pawlos_order.stock_requests.get()

    assert pawlos_order.fulfillment_status == "confirmed"
    assert request.transaction_number == pawlos_order.number
    assert request.customer == pawlos_order.customer
    assert balance(goods.chair, loc.PAW) == (50, 20)


@pytest.mark.django_db
def test_goods_from_pawlos_are_held_at_the_branch_for_the_customer(pawlos_order, staff, loc,
                                                                    goods, balance, walk_in,
                                                                    accounts):
    request = pawlos_order.stock_requests.get()
    requests.acknowledge_request(request=request, user=staff.store)
    release = requests.release_stock(request=request, storekeeper=staff.store,
                                     destination_type="branch",
                                     lines=[{"line_id": request.lines.get().pk, "qty": 20}])
    receive_transfer(transfer=release.transfer, user=staff.sales)

    line = pawlos_order.lines.get()
    line.refresh_from_db()
    assert line.qty_awaiting == 20
    assert balance(goods.chair, loc.PIA) == (20, 20)  # held: not free for other customers

    other = _order(staff, loc, walk_in, [{"product": goods.chair, "qty": 1}],
                   payment=None)
    _pay_full(staff, accounts, other)
    with pytest.raises(BusinessRuleError) as exc:
        sales.confirm_order(order=other, user=staff.sales)
    assert exc.value.code == "insufficient_stock"

    sales.release_from_branch(order=pawlos_order, user=staff.sales,
                              lines=[{"line_id": line.pk, "qty": 20}])
    pawlos_order.refresh_from_db()
    assert pawlos_order.fulfillment_status == "released"
    assert balance(goods.chair, loc.PIA) == (0, 0)
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_customer_pickup_at_pawlos_completes_the_sale(staff, loc, goods, abc, stock, balance):
    stock(goods.chair, loc.PAW, 50)
    order = sales.confirm_order(order=_order(
        staff, loc, abc, [{"product": goods.chair, "qty": 10, "source_location": loc.PAW}],
        channel="phone"), user=staff.sales)
    request = order.stock_requests.get()
    requests.acknowledge_request(request=request, user=staff.store)
    sales.mark_prepared(order=order, user=staff.store)

    requests.release_stock(request=request, storekeeper=staff.store,
                           destination_type="customer_pickup",
                           lines=[{"line_id": request.lines.get().pk, "qty": 10}])

    order.refresh_from_db()
    assert order.fulfillment_status == "released"
    assert DeliveryNote.objects.get(order=order).location == loc.PAW
    assert balance(goods.chair, loc.PAW) == (40, 0)
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_rejected_request_can_be_requested_again(pawlos_order, staff):
    request = pawlos_order.stock_requests.get()
    requests.reject_request(request=request, user=staff.store, reason="Damaged")
    line = pawlos_order.lines.get()
    assert sales.still_needed(pawlos_order, line) == 20

    again = sales.request_stock_for_order(order=pawlos_order, user=staff.sales,
                                          lines=[{"line_id": line.pk, "qty": 20}])

    assert again.transaction_number == pawlos_order.number
    with pytest.raises(BusinessRuleError) as exc:
        sales.request_stock_for_order(order=pawlos_order, user=staff.sales,
                                      lines=[{"line_id": line.pk, "qty": 1}])
    assert exc.value.code == "qty_exceeds_order"


# ---------------------------------------------------------------- cancel / void / return

@pytest.mark.django_db
def test_cancel_frees_stock_and_turns_payments_into_advance(pawlos_order, staff, accounts,
                                                            balance, goods, loc):
    payment = _pay_full(staff, accounts, pawlos_order)

    sales.cancel_order(order=pawlos_order, user=staff.sales, reason="Customer changed mind")

    pawlos_order.refresh_from_db()
    assert pawlos_order.fulfillment_status == "cancelled"
    assert pawlos_order.stock_requests.get().status == "cancelled"
    assert balance(goods.chair, loc.PAW) == (50, 0)
    assert money.payment_unallocated(payment) == payment.amount
    assert customer_balance(pawlos_order.customer)["outstanding"] == 0


@pytest.mark.django_db
def test_goods_on_the_way_for_a_cancelled_sale_arrive_as_free_stock(pawlos_order, staff, loc,
                                                                   goods, balance):
    request = pawlos_order.stock_requests.get()
    requests.acknowledge_request(request=request, user=staff.store)
    release = requests.release_stock(request=request, storekeeper=staff.store,
                                     destination_type="branch",
                                     lines=[{"line_id": request.lines.get().pk, "qty": 20}])
    sales.cancel_order(order=pawlos_order, user=staff.admin, reason="Customer left")

    receive_transfer(transfer=release.transfer, user=staff.sales)

    assert balance(goods.chair, loc.PIA) == (20, 0)
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_cancel_after_handover_is_refused(staff, loc, goods, abc, stock):
    stock(goods.desk, loc.PIA, 2)
    order = sales.confirm_order(order=_order(staff, loc, abc, [{"product": goods.desk,
                                                               "qty": 1}]), user=staff.sales)
    with pytest.raises(BusinessRuleError) as exc:
        sales.cancel_order(order=order, user=staff.sales, reason="x")
    assert exc.value.code == "already_released"


@pytest.mark.django_db
def test_void_reverses_stock_balance_and_payments(staff, loc, goods, abc, accounts, stock,
                                                  balance):
    stock(goods.desk, loc.PIA, 3)
    order = sales.confirm_order(order=_order(staff, loc, abc, [{"product": goods.desk,
                                                               "qty": 2}]), user=staff.sales)
    payment = _pay_full(staff, accounts, order)

    with pytest.raises(BusinessRuleError):
        sales.void_order(order=order, user=staff.accountant, reason="Wrong product")
    set_erp_permissions(staff.accountant, [ERPPermission.CORRECT_TRANSACTIONS])
    sales.void_order(order=order, user=staff.accountant, reason="Wrong product")

    order.refresh_from_db()
    assert order.fulfillment_status == "voided"
    assert balance(goods.desk, loc.PIA) == (3, 0)
    assert customer_balance(abc)["total_purchases"] == 0
    assert money.payment_unallocated(payment) == payment.amount

    fixed = _order(staff, loc, abc, [{"product": goods.cabinet, "qty": 2}], user=staff.admin,
                   replaces=order)
    assert fixed.replaces == order
    with pytest.raises(BusinessRuleError) as exc:
        _order(staff, loc, abc, [{"product": goods.cabinet, "qty": 1}], user=staff.admin,
               replaces=order)
    assert exc.value.code == "already_replaced"
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_return_lowers_total_stock_comes_back_and_overpayment_becomes_advance(
        staff, loc, goods, abc, accounts, stock, balance):
    stock(goods.desk, loc.PIA, 3)
    order = sales.confirm_order(order=_order(staff, loc, abc, [{"product": goods.desk,
                                                               "qty": 2}]), user=staff.sales)
    payment = _pay_full(staff, accounts, order)  # 40,000 paid

    sales.return_goods(order=order, user=staff.accountant, location=loc.PIA, reason="Scratched",
                       lines=[{"line_id": order.lines.get().pk, "qty": 1}])

    order.refresh_from_db()
    assert order.total_amount == D("20000")
    assert balance(goods.desk, loc.PIA) == (2, 0)
    assert money.order_paid(order) == D("20000")
    assert money.payment_unallocated(payment) == D("20000")
    assert order.payment_status == "paid"
    assert customer_balance(abc)["prepaid"] == D("20000")
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_returns_add_up_exactly_with_a_discount(staff, loc, goods, abc, stock):
    stock(goods.desk, loc.PIA, 3)
    order = sales.create_order(customer=abc, branch=loc.PIA, user=staff.accountant,
                               lines=[{"product": goods.desk, "qty": 3,
                                       "discount": D("100")}])  # 59,900
    order = sales.confirm_order(order=order, user=staff.accountant)
    line = order.lines.get()
    for _ in range(3):
        sales.return_goods(order=order, user=staff.accountant, location=loc.PIA, reason="x",
                           lines=[{"line_id": line.pk, "qty": 1}])
    order.refresh_from_db()
    assert order.total_amount == 0
