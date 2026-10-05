import pytest
from rest_framework.test import APIRequestFactory

from apps.accounts.models import ROLE_DEFAULT_PERMISSIONS, ERPPermission
from apps.accounts.permissions import erp_permission
from apps.audit.models import AuditLog

ACCOUNTANT_DEFAULTS = sorted(ROLE_DEFAULT_PERMISSIONS["accountant"])


@pytest.mark.django_db
def test_new_users_get_their_role_defaults(make_user):
    assert make_user(role="salesperson").erp_permissions == []
    assert make_user(role="storekeeper").erp_permissions == []
    assert make_user(role="accountant").erp_permissions == ACCOUNTANT_DEFAULTS


@pytest.mark.django_db
def test_accountant_corrects_sales_only_when_authorized(make_user):
    accountant = make_user(role="accountant")

    assert accountant.has_erp_permission(ERPPermission.CORRECT_PAYMENTS)
    assert not accountant.has_erp_permission(ERPPermission.CORRECT_TRANSACTIONS)


@pytest.mark.django_db
def test_admin_role_has_every_permission(make_user):
    admin = make_user(role="admin")

    assert all(admin.has_erp_permission(p) for p in ERPPermission.values)
    assert admin.effective_erp_permissions() == sorted(ERPPermission.values)


@pytest.mark.django_db
def test_admin_grants_and_removes_permissions_per_user(client_for, make_user):
    client, admin = client_for("admin")
    accountant = make_user(role="accountant")
    wanted = [ERPPermission.CORRECT_TRANSACTIONS, ERPPermission.VERIFY_PAYMENTS]

    response = client.patch(f"/api/v1/users/{accountant.id}/", {"permissions": wanted},
                            format="json")

    assert response.status_code == 200, response.data
    assert response.data["permissions"] == sorted(wanted)
    accountant.refresh_from_db()
    assert accountant.has_erp_permission(ERPPermission.CORRECT_TRANSACTIONS)
    assert not accountant.has_erp_permission(ERPPermission.EXPORT_REPORTS)
    log = AuditLog.objects.get(action="user_updated", object_id=str(accountant.id))
    assert log.actor == admin
    assert log.before["permissions"] == ACCOUNTANT_DEFAULTS
    assert log.after["permissions"] == sorted(wanted)


@pytest.mark.django_db
def test_create_user_with_explicit_permissions(client_for):
    client, _ = client_for("admin")

    response = client.post("/api/v1/users/", {
        "username": "sara", "role": "salesperson", "password": "Str0ng-pass-123",
        "permissions": [ERPPermission.APPROVE_DISCOUNTS],
    }, format="json")

    assert response.status_code == 201, response.data
    assert response.data["permissions"] == [ERPPermission.APPROVE_DISCOUNTS]


@pytest.mark.django_db
def test_role_change_resets_to_new_role_defaults(client_for, make_user):
    client, _ = client_for("admin")
    user = make_user(role="accountant")

    response = client.patch(f"/api/v1/users/{user.id}/", {"role": "salesperson"}, format="json")

    assert response.status_code == 200
    assert response.data["permissions"] == []


@pytest.mark.django_db
def test_unknown_permission_is_rejected(client_for, make_user):
    client, _ = client_for("admin")
    user = make_user()

    response = client.patch(f"/api/v1/users/{user.id}/", {"permissions": ["delete_everything"]},
                            format="json")

    assert response.status_code == 400


@pytest.mark.django_db
def test_me_returns_effective_permissions(client_for):
    client, _ = client_for("accountant")

    assert client.get("/api/v1/auth/me/").data["permissions"] == ACCOUNTANT_DEFAULTS


@pytest.mark.django_db
def test_permission_list_endpoint(client_for):
    client, _ = client_for("salesperson")

    rows = client.get("/api/v1/permissions/").data

    assert {r["codename"] for r in rows} == set(ERPPermission.values)
    verify = next(r for r in rows if r["codename"] == ERPPermission.VERIFY_PAYMENTS)
    assert set(verify["default_for_roles"]) == {"accountant", "admin"}


@pytest.mark.django_db
def test_erp_permission_class(make_user):
    check = erp_permission(ERPPermission.VERIFY_PAYMENTS)()
    request = APIRequestFactory().get("/")

    request.user = make_user(role="salesperson")
    assert not check.has_permission(request, None)

    request.user = make_user(role="accountant")
    assert check.has_permission(request, None)


@pytest.mark.django_db
def test_deactivated_user_has_no_erp_permissions(make_user):
    admin = make_user(role="admin", is_active=False)

    assert not admin.has_erp_permission(ERPPermission.VERIFY_PAYMENTS)
