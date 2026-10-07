"""What each customer owes, in the customer list (P-60) and its filters."""

from decimal import Decimal

import pytest

from apps.customers.selectors import customer_balance
from apps.payments import services as payments
from apps.sales import services as sales
from tests.factories import CustomerFactory


@pytest.fixture
def abc_owes_80k(staff, loc, goods, abc, accounts, stock):
    """ABC buys 100,000 on credit, pays 20,000, then gets a 50,000 limit."""
    stock(goods.cabinet, loc.PIA, 10)
    order = sales.create_order(customer=abc, branch=loc.PIA, user=staff.sales,
                               lines=[{"product": goods.cabinet, "qty": 5}])
    order = sales.confirm_order(order=order, user=staff.sales)
    payments.record_payment(customer=abc, account=accounts.org, amount=Decimal("20000"),
                            method="bank", recorded_by=staff.accountant, receipt_number="R-1",
                            allocations=[{"order": order, "line": None,
                                          "amount": Decimal("20000")}])
    abc.credit_limit = Decimal("50000")
    abc.save()
    return abc


def _by_name(response):
    return {row["name"]: row for row in response.data["results"]}


@pytest.mark.django_db
def test_list_shows_what_each_customer_owes(api_client, staff, abc_owes_80k):
    CustomerFactory(name="Paid up")
    api_client.force_authenticate(staff.sales)

    rows = _by_name(api_client.get("/api/v1/customers/"))

    assert rows["ABC Furniture"]["outstanding"] == "80000.00"
    assert rows["ABC Furniture"]["outstanding"] == str(
        customer_balance(abc_owes_80k)["outstanding"])
    assert rows["ABC Furniture"]["over_limit"] is True
    assert (rows["Paid up"]["outstanding"], rows["Paid up"]["over_limit"]) == ("0.00", False)


@pytest.mark.django_db
def test_filters_has_balance_and_over_limit(api_client, staff, abc_owes_80k):
    CustomerFactory(name="Paid up")
    api_client.force_authenticate(staff.accountant)

    owing = _by_name(api_client.get("/api/v1/customers/", {"has_balance": "true"}))
    over = _by_name(api_client.get("/api/v1/customers/", {"over_limit": "true"}))
    clear = _by_name(api_client.get("/api/v1/customers/", {"has_balance": "false"}))

    assert set(owing) == {"ABC Furniture"}
    assert set(over) == {"ABC Furniture"}
    assert "ABC Furniture" not in clear and "Paid up" in clear


@pytest.mark.django_db
def test_within_limit_is_not_over(api_client, staff, abc_owes_80k):
    abc_owes_80k.credit_limit = Decimal("80000")
    abc_owes_80k.save()
    api_client.force_authenticate(staff.accountant)

    row = _by_name(api_client.get("/api/v1/customers/"))["ABC Furniture"]

    assert row["over_limit"] is False


@pytest.mark.django_db
def test_owing_without_credit_is_over_limit(api_client, staff, loc, goods, stock):
    """The accountant approved a credit sale for a customer who has no credit terms."""
    cash_only = CustomerFactory(name="Cash only", credit_allowed=False)
    stock(goods.desk, loc.PIA, 1)
    order = sales.create_order(customer=cash_only, branch=loc.PIA, user=staff.accountant,
                               lines=[{"product": goods.desk, "qty": 1}])
    sales.confirm_order(order=order, user=staff.accountant)
    api_client.force_authenticate(staff.accountant)

    row = _by_name(api_client.get("/api/v1/customers/", {"over_limit": "true"}))["Cash only"]

    assert row["outstanding"] == "20000.00"


@pytest.mark.django_db
def test_order_by_outstanding_and_detail_has_it(api_client, staff, abc_owes_80k):
    CustomerFactory(name="Paid up")
    api_client.force_authenticate(staff.accountant)

    first = api_client.get("/api/v1/customers/", {"ordering": "-outstanding"}).data["results"][0]
    detail = api_client.get(f"/api/v1/customers/{abc_owes_80k.pk}/").data

    assert first["name"] == "ABC Furniture"
    assert detail["outstanding"] == "80000.00"


@pytest.mark.django_db
def test_create_and_edit_responses_include_the_balance(api_client, staff, abc_owes_80k):
    api_client.force_authenticate(staff.accountant)

    created = api_client.post("/api/v1/customers/", {"name": "New shop"}, format="json")
    edited = api_client.patch(f"/api/v1/customers/{abc_owes_80k.pk}/", {"city": "Jimma"},
                              format="json")

    assert created.status_code == 201 and created.data["outstanding"] == "0.00"
    assert edited.status_code == 200 and edited.data["outstanding"] == "80000.00"
