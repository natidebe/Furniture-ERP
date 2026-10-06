import pytest

from apps.audit.models import AuditLog
from apps.locations.models import Location


@pytest.mark.django_db
def test_seeded_locations():
    rows = {loc.code: loc for loc in Location.objects.select_related("parent")}

    assert set(rows) >= {"PIA", "PIA-UG", "DEN", "PAW"}
    assert rows["PIA-UG"].parent.code == "PIA"
    assert rows["PIA-UG"].type == "sub_store"
    assert rows["PAW"].can_release and rows["PAW"].can_sell
    assert not any(rows[c].can_release for c in ("PIA", "PIA-UG", "DEN"))


@pytest.mark.django_db
def test_any_staff_can_list_locations(client_for):
    client, _ = client_for("storekeeper")

    response = client.get("/api/v1/locations/")

    assert response.status_code == 200
    assert response.data["count"] >= 4


@pytest.mark.django_db
def test_salesperson_cannot_create_location(client_for):
    client, _ = client_for("salesperson")

    response = client.post("/api/v1/locations/",
                           {"code": "BOL", "name": "Bole", "type": "shop"}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_creates_location_code_upper_cased_and_audited(client_for):
    client, admin = client_for("admin")

    response = client.post("/api/v1/locations/",
                           {"code": "bol", "name": "Bole Branch", "type": "shop",
                            "can_sell": True}, format="json")

    assert response.status_code == 201, response.data
    location = Location.objects.get(code="BOL")
    assert location.created_by == admin
    assert AuditLog.objects.filter(action="location_created",
                                   object_id=str(location.id)).exists()


@pytest.mark.django_db
def test_duplicate_code_rejected(client_for):
    client, _ = client_for("admin")

    response = client.post("/api/v1/locations/",
                           {"code": "pia", "name": "Copy", "type": "shop"}, format="json")

    assert response.status_code == 400
    assert "code" in response.data
