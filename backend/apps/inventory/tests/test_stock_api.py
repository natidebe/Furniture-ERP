import pytest

from apps.inventory import services
from apps.inventory.models import StockMovement
from tests.factories import ProductFactory


@pytest.mark.django_db
def test_summary_matrix_columns_and_total_include_transit(client_for, staff, loc, product,
                                                          stock):
    stock(product, loc.PAW, 100)
    stock(product, loc.PIA, 10)
    stock(product, loc.DEN, 5)
    services.create_transfer(from_location=loc.PAW, to_location=loc.DEN,
                             lines=[{"product": product, "qty": 7}], user=staff.admin)
    client, _ = client_for("salesperson", home_location=loc.PIA)

    response = client.get("/api/v1/stock/summary/")

    assert response.status_code == 200
    assert [c["code"] for c in response.data["locations"]] == [
        "PIA", "PIA-UG", "DEN", "PAW", "TRANSIT"]
    row = response.data["results"][0]
    on_hand = {code: cell["on_hand"] for code, cell in row["stock"].items()}
    assert on_hand == {"PIA": 10, "PIA-UG": 0, "DEN": 5, "PAW": 93, "TRANSIT": 7}
    assert row["in_transit"] == 7
    assert row["total"] == 115 == sum(on_hand.values())


@pytest.mark.django_db
def test_summary_low_filter(client_for, loc, stock):
    low = ProductFactory(code="LOW-1", min_stock=10)
    fine = ProductFactory(code="OK-1", min_stock=10)
    stock(low, loc.PAW, 7)
    stock(fine, loc.PAW, 10)
    client, _ = client_for("admin")

    response = client.get("/api/v1/stock/summary/", {"low": "true"})

    assert [r["code"] for r in response.data["results"]] == ["LOW-1"]
    assert response.data["results"][0]["low_stock"] is True


@pytest.mark.django_db
def test_product_stock_card(client_for, loc, product, stock):
    stock(product, loc.PAW, 30)
    stock(product, loc.PIA, 4)
    client, _ = client_for("salesperson", home_location=loc.PIA)

    response = client.get(f"/api/v1/products/{product.pk}/stock/")

    assert response.status_code == 200
    assert response.data["code"] == "VC-001"
    assert response.data["stock"]["PAW"]["available"] == 30
    assert response.data["total"] == 34


@pytest.mark.django_db
def test_balance_list_shows_available(client_for, loc, product, stock):
    stock(product, loc.PAW, 10)
    services.reserve(product=product, location=loc.PAW, qty=3)
    client, _ = client_for("salesperson", home_location=loc.PIA)

    response = client.get("/api/v1/stock/", {"location": loc.PAW.pk})

    row = response.data["results"][0]
    assert (row["on_hand"], row["reserved"], row["available"]) == (10, 3, 7)


@pytest.mark.django_db
def test_movements_scoped_to_storekeepers_location(api_client, make_user, loc, product, stock):
    stock(product, loc.PAW, 5)
    stock(product, loc.DEN, 5)

    api_client.force_authenticate(make_user(role="storekeeper", home_location=loc.PAW))
    paw = api_client.get("/api/v1/stock/movements/").data
    api_client.force_authenticate(make_user(role="accountant"))
    everything = api_client.get("/api/v1/stock/movements/").data
    api_client.force_authenticate(make_user(role="salesperson", home_location=loc.PIA))
    sales = api_client.get("/api/v1/stock/movements/")

    assert paw["count"] == 1 and paw["results"][0]["to_location_code"] == "PAW"
    assert everything["count"] == 2
    assert sales.status_code == 403


@pytest.mark.django_db
def test_movement_filter_by_transaction(client_for, loc, product, stock):
    receipt = stock(product, loc.PAW, 5)
    stock(product, loc.PAW, 5)
    client, _ = client_for("admin")

    response = client.get("/api/v1/stock/movements/", {"transaction": receipt.number})

    assert response.data["count"] == 1


@pytest.mark.django_db
def test_reverse_endpoint_needs_permission_and_reason(api_client, make_user, loc, product,
                                                      stock):
    stock(product, loc.PAW, 5)
    movement = StockMovement.objects.get()
    url = f"/api/v1/stock/movements/{movement.pk}/reverse/"

    api_client.force_authenticate(make_user(role="accountant"))
    assert api_client.post(url, {"reason": "x"}, format="json").status_code == 403

    api_client.force_authenticate(make_user(role="admin"))
    assert api_client.post(url, {}, format="json").status_code == 400
    response = api_client.post(url, {"reason": "Wrong container"}, format="json")
    assert response.status_code == 201, response.data
    assert response.data["type"] == "reversal"


@pytest.mark.django_db
def test_goods_receipt_api_defaults_to_pawlos(client_for, loc, product, balance):
    client, user = client_for("storekeeper", home_location=loc.PAW)

    response = client.post("/api/v1/goods-receipts/", {
        "reference": "Container 12", "lines": [{"product": product.pk, "qty": 40}]},
        format="json")

    assert response.status_code == 201, response.data
    assert response.data["lines"] == [{"product": product.pk, "product_code": "VC-001",
                                       "product_name": "Visitor chair", "qty": 40}]
    assert response.data["location_code"] == "PAW"
    assert response.data["received_by_name"] == user.full_name
    assert balance(product, loc.PAW) == (40, 0)


@pytest.mark.django_db
def test_lists_name_the_people_involved(api_client, staff, loc, product, stock):
    """Adjustments and transfers carry names for the web lists, not only user ids."""
    from apps.inventory import services

    stock(product, loc.PAW, 10)
    adjustment = services.propose_adjustment(location=loc.PAW, product=product, qty_delta=-1,
                                             reason="damage", user=staff.store)
    services.approve_adjustment(adjustment=adjustment, user=staff.accountant)
    services.send_transfer(from_location=loc.PAW, to_location=loc.PIA,
                           lines=[{"product": product, "qty": 2}], user=staff.admin)
    api_client.force_authenticate(staff.admin)

    adj = api_client.get("/api/v1/adjustments/").data["results"][0]
    transfer = api_client.get("/api/v1/transfers/").data["results"][0]

    assert (adj["proposed_by_name"], adj["decided_by_name"]) == (
        staff.store.full_name, staff.accountant.full_name)
    assert (transfer["sent_by_name"], transfer["received_by_name"]) == (
        staff.admin.full_name, None)
    assert transfer["lines"][0]["product_name"] == "Visitor chair"


@pytest.mark.django_db
def test_transit_location_cannot_be_edited(client_for, loc):
    client, _ = client_for("admin")

    response = client.patch(f"/api/v1/locations/{loc.TRANSIT.pk}/", {"is_active": False},
                            format="json")

    assert response.status_code == 400
    assert response.data["code"] == "system_location"
