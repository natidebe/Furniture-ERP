"""GET /dashboard/ — the home page for each role in one call (P-02)."""

from decimal import Decimal

import pytest

from apps.requests import services as requests
from apps.sales import services as sales
from tests.factories import CustomerFactory

URL = "/api/v1/dashboard/"


@pytest.fixture
def credit_sale(staff, loc, goods, abc, stock):
    """An unpaid 100,000 sale by the Piassa salesperson; ABC's limit is then 50,000."""
    stock(goods.cabinet, loc.PIA, 10)
    order = sales.create_order(customer=abc, branch=loc.PIA, user=staff.sales,
                               lines=[{"product": goods.cabinet, "qty": 5}])
    order = sales.confirm_order(order=order, user=staff.sales)
    abc.credit_limit = Decimal("50000")
    abc.save()
    return order


@pytest.mark.django_db
def test_salesperson_dashboard(api_client, staff, credit_sale):
    api_client.force_authenticate(staff.sales)

    data = api_client.get(URL).data

    assert data["role"] == "salesperson"
    assert data["sales_today"]["sales"] == "100000.00"
    assert data["sales_today"]["transactions"] == 1
    assert data["waiting_for_payment"]["count"] == 1
    assert data["waiting_for_payment"]["items"][0]["number"] == credit_sale.number
    for block in ("open_requests", "transfers_arriving", "held_for_customers"):
        assert set(data[block]) == {"count", "items"}


@pytest.mark.django_db
def test_salesperson_sees_only_own_sales(api_client, staff, credit_sale):
    api_client.force_authenticate(staff.den_sales)

    data = api_client.get(URL).data

    assert data["sales_today"]["transactions"] == 0
    assert data["waiting_for_payment"]["count"] == 0


@pytest.mark.django_db
def test_storekeeper_queue_puts_pending_first(api_client, staff, loc, goods, stock):
    stock(goods.chair, loc.PAW, 50)
    first = requests.create_stock_request(
        requesting_location=loc.PIA, source_location=loc.PAW, salesperson=staff.sales,
        lines=[{"product": goods.chair, "qty": 5}])
    requests.acknowledge_request(request=first, user=staff.store)
    second = requests.create_stock_request(
        requesting_location=loc.DEN, source_location=loc.PAW, salesperson=staff.den_sales,
        lines=[{"product": goods.chair, "qty": 2}])
    api_client.force_authenticate(staff.store)

    data = api_client.get(URL).data

    queue = data["request_queue"]
    assert [r["number"] for r in queue["items"]] == [second.number, first.number]
    assert queue["items"][0]["lines"] == "2 × VC-001"
    assert data["recent_movements"]["count"] >= 1
    assert "low_stock" in data and "transfers_not_received" in data


@pytest.mark.django_db
def test_accountant_dashboard(api_client, staff, credit_sale):
    CustomerFactory(name="Paid up")
    api_client.force_authenticate(staff.accountant)

    data = api_client.get(URL).data

    assert data["role"] == "accountant"
    assert data["today"]["credit"] == "100000.00"
    assert "by_branch" not in data["today"]
    over = data["customers_over_limit"]
    assert over["count"] == 1
    assert over["items"][0]["outstanding"] == "100000.00"
    for block in ("payments_to_verify", "adjustments_to_approve", "transfers_with_shortages"):
        assert "count" in data[block] and "items" in data[block]
    assert "low_stock" not in data


@pytest.mark.django_db
def test_admin_dashboard_adds_branches_and_low_stock(api_client, staff, credit_sale):
    api_client.force_authenticate(staff.admin)

    data = api_client.get(URL).data

    assert data["today"]["by_branch"][0]["branch"] == "PIA"
    assert data["today"]["by_salesperson"][0]["sales"] == "100000.00"
    assert "low_stock" in data


@pytest.mark.django_db
def test_dashboard_needs_login(api_client):
    assert api_client.get(URL).status_code == 401
