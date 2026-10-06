import pytest

from apps.audit.models import AuditLog
from apps.customers.models import Customer


@pytest.mark.django_db
def test_salesperson_creates_customer_but_not_credit_terms(client_for):
    client, _ = client_for("salesperson")

    response = client.post("/api/v1/customers/", {
        "name": "Jimma Office Furniture", "phone": "0911000000", "city": "Jimma",
        "type": "out_of_city", "credit_allowed": True, "credit_limit": "50000"},
        format="json")

    assert response.status_code == 201, response.data
    customer = Customer.objects.get(name="Jimma Office Furniture")
    assert (customer.credit_allowed, customer.credit_limit) == (False, None)  # read-only


@pytest.mark.django_db
def test_accountant_sets_credit_terms_and_it_is_audited(client_for):
    client, _ = client_for("accountant")
    customer = Customer.objects.create(name="ABC Furniture", type="reseller")

    response = client.patch(f"/api/v1/customers/{customer.pk}/",
                            {"credit_allowed": True, "credit_limit": "150000"}, format="json")

    assert response.status_code == 200, response.data
    customer.refresh_from_db()
    assert customer.credit_allowed and customer.credit_limit == 150000
    assert AuditLog.objects.filter(action="customer_updated",
                                   object_id=str(customer.pk)).exists()


@pytest.mark.django_db
def test_shared_phone_gives_a_warning_not_an_error(client_for):
    Customer.objects.create(name="Shop A", phone="0911222333")
    client, _ = client_for("salesperson")

    response = client.post("/api/v1/customers/", {"name": "Shop B", "phone": "0911222333"},
                           format="json")

    assert response.status_code == 201
    assert "Shop A" in response.data["warnings"][0]


@pytest.mark.django_db
def test_search_by_name_phone_shop(client_for):
    Customer.objects.create(name="Abebe", shop_name="Bole Furniture", phone="0922")
    client, _ = client_for("salesperson")

    for q in ("abebe", "bole", "0922"):
        assert client.get("/api/v1/customers/", {"search": q}).data["count"] == 1


@pytest.mark.django_db
def test_storekeeper_has_no_customer_access(client_for):
    client, _ = client_for("storekeeper")

    assert client.get("/api/v1/customers/").status_code == 403
