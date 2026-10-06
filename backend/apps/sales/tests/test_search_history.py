import pytest

from apps.payments import services as payments
from apps.requests import services as requests
from apps.sales import services as sales


@pytest.fixture
def pickup_sale(staff, loc, goods, abc, accounts, stock):
    stock(goods.chair, loc.PAW, 30)
    order = sales.confirm_order(order=sales.create_order(
        customer=abc, branch=loc.PIA, user=staff.sales, channel="phone",
        lines=[{"product": goods.chair, "qty": 5, "source_location": loc.PAW}]),
        user=staff.sales)
    request = order.stock_requests.get()
    requests.acknowledge_request(request=request, user=staff.store)
    release = requests.release_stock(request=request, storekeeper=staff.store,
                                     destination_type="customer_pickup",
                                     lines=[{"line_id": request.lines.get().pk, "qty": 5}])
    payment = payments.record_payment(
        customer=abc, account=accounts.org, amount="10000", method="bank",
        recorded_by=staff.accountant, receipt_number="R-77",
        allocations=[{"order": order, "amount": "10000"}])
    return order, request, release, payment


@pytest.mark.django_db
def test_history_is_the_same_from_any_number(client_for, pickup_sale):
    order, request, release, payment = pickup_sale
    client, _ = client_for("accountant")
    note = order.delivery_notes.get()

    views = [client.get(f"/api/v1/transactions/{n}/").data
             for n in (order.number, request.number, release.number, note.number,
                       payment.number)]

    assert {v["header"]["transaction"] for v in views} == {order.number}
    events = [e["event"] for e in views[0]["events"]]
    assert events[:2] == ["created", "confirmed"]
    assert {"stock requested", "acknowledged", "released", "handed over",
            "payment recorded"} <= set(events)


@pytest.mark.django_db
def test_history_hidden_from_other_salespeople(client_for, pickup_sale, loc):
    order = pickup_sale[0]
    client, _ = client_for("salesperson", home_location=loc.PIA)

    assert client.get(f"/api/v1/transactions/{order.number}/").status_code == 404
    assert client.get("/api/v1/transactions/SO-1999-00001/").status_code == 404


@pytest.mark.django_db
def test_search_finds_everything(client_for, pickup_sale):
    order, request, _, payment = pickup_sale
    client, _ = client_for("accountant")

    def search(q):
        return client.get("/api/v1/search/", {"q": q}).data

    product_hit = search("vc-001")
    assert product_hit["exact"]["kind"] == "product"
    assert product_hit["products"][0]["stock"]["PAW"] == 25
    assert search("ABC Furn")["customers"][0]["name"] == "ABC Furniture"
    assert search(order.number)["exact"] == {"kind": "order", "id": order.pk,
                                             "number": order.number}
    assert search(request.number)["exact"]["kind"] == "stock_request"
    assert search("R-77")["payments"][0]["number"] == payment.number
    assert search(order.delivery_notes.get().number)["exact"]["kind"] == "delivery_note"
    assert search(order.customer.phone)["orders"][0]["number"] == order.number


@pytest.mark.django_db
def test_search_respects_scope(client_for, pickup_sale, loc):
    order = pickup_sale[0]
    other, _ = client_for("salesperson", home_location=loc.PIA)

    assert other.get("/api/v1/search/", {"q": order.number}).data["orders"] == []
