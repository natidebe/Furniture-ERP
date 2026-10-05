from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.catalog.models import Category, Product, Unit
from tests.factories import ProductFactory


@pytest.mark.django_db
def test_seeded_units_and_categories():
    assert set(Unit.objects.values_list("symbol", flat=True)) >= {"pcs", "set"}
    assert Category.objects.filter(name="Executive chairs").exists()
    assert Category.objects.count() >= 8


@pytest.mark.django_db
def test_code_is_stored_upper_case():
    product = ProductFactory(code="  vc-001 ")

    product.refresh_from_db()
    assert product.code == "VC-001"


@pytest.mark.django_db
def test_code_is_unique_regardless_of_case():
    ProductFactory(code="VC-001")

    with pytest.raises(IntegrityError):
        ProductFactory(code="vc-001")


@pytest.mark.django_db
def test_product_has_no_cost_fields():
    names = {f.name for f in Product._meta.get_fields()}

    assert not names & {"cost", "cost_price", "purchase_price", "profit"}


def _product_payload(**overrides):
    category = Category.objects.get(name="Visitor chairs")
    unit = Unit.objects.get(symbol="pcs")
    return {"code": "vc-010", "name": "Visitor chair mesh", "category": category.id,
            "unit": unit.id, "selling_price": "3200.00", "min_stock": 5, **overrides}


@pytest.mark.django_db
def test_admin_creates_product(client_for):
    client, admin = client_for("admin")

    response = client.post("/api/v1/products/", _product_payload(), format="json")

    assert response.status_code == 201, response.data
    assert response.data["code"] == "VC-010"
    assert Product.objects.get(code="VC-010").created_by == admin


@pytest.mark.django_db
def test_duplicate_code_returns_400_not_500(client_for):
    client, _ = client_for("admin")
    ProductFactory(code="VC-010")

    response = client.post("/api/v1/products/", _product_payload(), format="json")

    assert response.status_code == 400
    assert "code" in response.data


@pytest.mark.django_db
def test_patch_ignores_selling_price(client_for):
    client, _ = client_for("admin")
    product = ProductFactory(selling_price=Decimal("1000.00"))

    response = client.patch(f"/api/v1/products/{product.id}/",
                            {"name": "Renamed", "selling_price": "1.00"}, format="json")

    assert response.status_code == 200
    product.refresh_from_db()
    assert product.name == "Renamed"
    assert product.selling_price == Decimal("1000.00")


@pytest.mark.django_db
def test_search_by_code_and_name(client_for):
    client, _ = client_for("salesperson")
    ProductFactory(code="VC-001", name="Visitor chair black")
    ProductFactory(code="DS-003", name="Manager desk")

    by_code = client.get("/api/v1/products/", {"search": "vc-001"})
    by_name = client.get("/api/v1/products/", {"search": "desk"})

    assert [p["code"] for p in by_code.data["results"]] == ["VC-001"]
    assert [p["code"] for p in by_name.data["results"]] == ["DS-003"]


@pytest.mark.django_db
def test_salesperson_cannot_create_or_reprice(client_for):
    client, _ = client_for("salesperson")
    product = ProductFactory()

    assert client.post("/api/v1/products/", _product_payload(),
                       format="json").status_code == 403
    assert client.post(f"/api/v1/products/{product.id}/change-price/",
                       {"new_price": "10.00"}, format="json").status_code == 403


@pytest.mark.django_db
def test_categories_and_units_are_readable(client_for):
    client, _ = client_for("salesperson")

    assert client.get("/api/v1/categories/").status_code == 200
    assert client.get("/api/v1/units/").status_code == 200
