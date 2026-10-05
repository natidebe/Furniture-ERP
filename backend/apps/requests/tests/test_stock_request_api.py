import pytest

from apps.requests.models import StockRequest


@pytest.fixture
def pawlos_stock(loc, product, stock):
    stock(product, loc.PAW, 50)


@pytest.mark.django_db
def test_salesperson_creates_request_with_defaults(client_for, loc, product, pawlos_stock):
    client, sales = client_for("salesperson", home_location=loc.PIA)

    response = client.post("/api/v1/stock-requests/", {
        "lines": [{"product": product.pk, "qty": 10}], "reference": "Walk-in, Abebe",
        "notes": "Customer waiting"}, format="json")

    assert response.status_code == 201, response.data
    assert response.data["requesting_location_code"] == "PIA"
    assert response.data["source_location_code"] == "PAW"
    assert response.data["lines"][0]["qty_remaining"] == 10
    assert StockRequest.objects.get().salesperson == sales


@pytest.mark.django_db
def test_storekeeper_cannot_create_requests(client_for, loc, product, pawlos_stock):
    client, _ = client_for("storekeeper", home_location=loc.PAW)

    response = client.post("/api/v1/stock-requests/", {
        "requesting_location": loc.PIA.pk, "lines": [{"product": product.pk, "qty": 1}]},
        format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_full_flow_over_the_api(api_client, make_user, loc, product, pawlos_stock):
    sales = make_user(role="salesperson", home_location=loc.PIA)
    store = make_user(role="storekeeper", home_location=loc.PAW)

    api_client.force_authenticate(sales)
    created = api_client.post("/api/v1/stock-requests/",
                              {"lines": [{"product": product.pk, "qty": 10}]}, format="json")
    request_id, line_id = created.data["id"], created.data["lines"][0]["id"]

    api_client.force_authenticate(store)
    assert api_client.post(f"/api/v1/stock-requests/{request_id}/acknowledge/").status_code == 200
    release = api_client.post(f"/api/v1/stock-requests/{request_id}/release/", {
        "destination_type": "branch", "lines": [{"line_id": line_id, "qty": 6}]}, format="json")
    assert release.status_code == 201, release.data
    assert release.data["number"].startswith("SRL-")
    assert release.data["transfer_number"].startswith("TR-")

    detail = api_client.get(f"/api/v1/stock-requests/{request_id}/").data
    assert detail["status"] == "partially_released"
    assert detail["lines"][0]["qty_remaining"] == 4


@pytest.mark.django_db
def test_business_errors_come_back_as_400_with_code(api_client, make_user, loc, product,
                                                     pawlos_stock):
    sales = make_user(role="salesperson", home_location=loc.PIA)
    store = make_user(role="storekeeper", home_location=loc.PAW)
    api_client.force_authenticate(sales)
    created = api_client.post("/api/v1/stock-requests/",
                              {"lines": [{"product": product.pk, "qty": 10}]}, format="json")

    api_client.force_authenticate(store)
    response = api_client.post(f"/api/v1/stock-requests/{created.data['id']}/release/", {
        "destination_type": "branch",
        "lines": [{"line_id": created.data["lines"][0]["id"], "qty": 1}]}, format="json")

    assert response.status_code == 400
    assert response.data["code"] == "invalid_state"


@pytest.mark.django_db
def test_list_is_scoped_by_role(api_client, make_user, loc, product, pawlos_stock):
    from apps.requests.services import create_stock_request

    pia = make_user(role="salesperson", home_location=loc.PIA)
    den = make_user(role="salesperson", home_location=loc.DEN)
    for user, location in ((pia, loc.PIA), (den, loc.DEN)):
        create_stock_request(requesting_location=location, source_location=loc.PAW,
                             lines=[{"product": product, "qty": 1}], salesperson=user)

    def numbers_for(user):
        api_client.force_authenticate(user)
        return api_client.get("/api/v1/stock-requests/").data["count"]

    assert numbers_for(pia) == 1
    assert numbers_for(den) == 1
    assert numbers_for(make_user(role="storekeeper", home_location=loc.PAW)) == 2
    assert numbers_for(make_user(role="storekeeper", home_location=loc.DEN)) == 0
    assert numbers_for(make_user(role="accountant")) == 2


@pytest.mark.django_db
def test_salesperson_cannot_release(client_for, loc, product, pawlos_stock):
    client, _ = client_for("salesperson", home_location=loc.PIA)
    created = client.post("/api/v1/stock-requests/",
                          {"lines": [{"product": product.pk, "qty": 1}]}, format="json")

    response = client.post(f"/api/v1/stock-requests/{created.data['id']}/release/", {
        "destination_type": "branch", "lines": [{"line_id": 1, "qty": 1}]}, format="json")

    assert response.status_code == 403
