import pytest
from django.contrib.auth.models import Group

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.locations.models import Location


@pytest.mark.django_db
def test_role_groups_exist():
    assert set(Group.objects.values_list("name", flat=True)) >= {
        "salesperson", "storekeeper", "accountant", "admin"}


@pytest.mark.django_db
def test_user_group_follows_role(make_user):
    user = make_user(role="salesperson")
    assert list(user.groups.values_list("name", flat=True)) == ["salesperson"]

    user.role = "storekeeper"
    user.save()

    assert list(user.groups.values_list("name", flat=True)) == ["storekeeper"]


@pytest.mark.django_db
def test_createsuperuser_is_admin():
    user = User.objects.create_superuser("owner", password="x")
    assert user.role == "admin"


@pytest.mark.django_db
def test_admin_creates_user_and_it_is_audited(client_for):
    client, admin = client_for("admin")
    pawlos = Location.objects.get(code="PAW")

    response = client.post("/api/v1/users/", {
        "username": "store1", "full_name": "Store Keeper", "role": "storekeeper",
        "home_location": pawlos.id, "password": "Str0ng-pass-123",
    }, format="json")

    assert response.status_code == 201, response.data
    assert "password" not in response.data
    user = User.objects.get(username="store1")
    assert user.check_password("Str0ng-pass-123")
    log = AuditLog.objects.get(action="user_created", object_id=str(user.id))
    assert log.actor == admin
    assert log.after["role"] == "storekeeper"


@pytest.mark.django_db
def test_role_change_is_audited(client_for, make_user):
    client, _ = client_for("admin")
    user = make_user(role="salesperson")

    response = client.patch(f"/api/v1/users/{user.id}/", {"role": "accountant"}, format="json")

    assert response.status_code == 200
    log = AuditLog.objects.get(action="user_updated", object_id=str(user.id))
    assert log.before["role"] == "salesperson"
    assert log.after["role"] == "accountant"


@pytest.mark.django_db
def test_users_cannot_be_deleted(client_for, make_user):
    client, _ = client_for("admin")
    user = make_user()

    assert client.delete(f"/api/v1/users/{user.id}/").status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["salesperson", "storekeeper", "accountant"])
def test_only_admin_manages_users(client_for, role):
    client, _ = client_for(role)

    assert client.get("/api/v1/users/").status_code == 403
    assert client.post("/api/v1/users/", {"username": "x", "password": "y"},
                       format="json").status_code == 403
