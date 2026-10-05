import pytest
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.audit.services import audit_log
from apps.locations.models import Location
from tests.factories import ProductFactory


@pytest.mark.django_db
def test_audit_log_outside_request_is_system(make_user):
    location = Location.objects.get(code="PAW")

    log = audit_log(actor=make_user(), action="test", obj=location, after={"a": 1})

    assert log.source == "system"
    assert log.ip is None
    assert log.model == "locations.Location"
    assert log.object_id == str(location.pk)


@pytest.mark.django_db
def test_request_ip_and_bot_source_are_recorded(client_for):
    client, _ = client_for("admin")
    product = ProductFactory()

    client.post(f"/api/v1/products/{product.id}/change-price/", {"new_price": "99.00"},
                format="json", REMOTE_ADDR="196.188.1.20", HTTP_X_CLIENT="bot")

    log = AuditLog.objects.get(action="price_change")
    assert log.source == "bot"
    assert log.ip == "196.188.1.20"


@pytest.mark.django_db
def test_web_requests_are_web_source(client_for):
    client, _ = client_for("admin")
    product = ProductFactory()

    client.post(f"/api/v1/products/{product.id}/change-price/", {"new_price": "99.00"},
                format="json")

    assert AuditLog.objects.get(action="price_change").source == "web"


@pytest.mark.django_db
def test_simple_history_tracks_products():
    product = ProductFactory(name="Before")
    product.name = "After"
    product.save()

    assert [h.name for h in product.history.order_by("history_id")] == ["Before", "After"]


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", [
    ("salesperson", 403), ("storekeeper", 403), ("accountant", 200), ("admin", 200)])
def test_audit_endpoint_permissions(client_for, role, status):
    client, _ = client_for(role)

    assert client.get("/api/v1/audit/").status_code == status


@pytest.mark.django_db
def test_audit_endpoint_is_read_only(client_for):
    client, _ = client_for("admin")

    assert client.post("/api/v1/audit/", {}, format="json").status_code == 405


@pytest.mark.django_db
def test_audit_endpoint_filters(client_for, make_user):
    client, _ = client_for("accountant")
    product = ProductFactory()
    other = ProductFactory()
    actor = make_user(role="admin")
    audit_log(actor=actor, action="price_change", obj=product)
    audit_log(actor=actor, action="price_change", obj=other)

    response = client.get("/api/v1/audit/", {"model": "catalog.Product",
                                             "object_id": str(product.pk)})
    assert [row["object_id"] for row in response.data["results"]] == [str(product.pk)]

    today = timezone.localdate(AuditLog.objects.first().at).isoformat()
    assert client.get("/api/v1/audit/", {"from": today}).data["count"] == 2
    assert client.get("/api/v1/audit/", {"to": "2000-01-01"}).data["count"] == 0
