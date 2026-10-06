from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.catalog.models import Category, PriceHistory, Unit
from apps.catalog.selectors import price_for
from apps.catalog.services import change_price
from apps.core.exceptions import BusinessRuleError
from tests.factories import CustomerFactory, ProductFactory


@pytest.mark.django_db
def test_resellers_pay_wholesale_everyone_else_the_selling_price():
    product = ProductFactory(selling_price=Decimal("2500"), wholesale_price=Decimal("2200"))

    assert price_for(product, CustomerFactory(type="reseller")) == Decimal("2200")
    assert price_for(product, CustomerFactory(type="walk_in")) == Decimal("2500")
    assert price_for(product, CustomerFactory(type="out_of_city")) == Decimal("2500")
    assert price_for(product) == Decimal("2500")


@pytest.mark.django_db
def test_reseller_pays_selling_price_when_no_wholesale_price_is_set():
    product = ProductFactory(selling_price=Decimal("2500"), wholesale_price=None)

    assert price_for(product, CustomerFactory(type="reseller")) == Decimal("2500")


@pytest.mark.django_db
def test_change_wholesale_price_is_recorded_separately(make_user):
    admin = make_user(role="admin")
    product = ProductFactory(selling_price=Decimal("2500"))

    change_price(product=product, new_price=Decimal("2200"), user=admin,
                 price_type="wholesale", reason="Reseller list 2026")

    product.refresh_from_db()
    assert product.wholesale_price == Decimal("2200")
    assert product.selling_price == Decimal("2500")
    history = PriceHistory.objects.get()
    assert (history.price_type, history.old_price, history.new_price) == (
        "wholesale", None, Decimal("2200"))
    log = AuditLog.objects.get(action="price_change")
    assert log.after == {"wholesale_price": "2200"}


@pytest.mark.django_db
def test_wholesale_cannot_be_above_selling(make_user):
    admin = make_user(role="admin")
    product = ProductFactory(selling_price=Decimal("2500"), wholesale_price=Decimal("2200"))

    with pytest.raises(BusinessRuleError) as exc:
        change_price(product=product, new_price=Decimal("2600"), user=admin,
                     price_type="wholesale")
    assert exc.value.code == "wholesale_above_selling"

    with pytest.raises(BusinessRuleError) as exc:
        change_price(product=product, new_price=Decimal("2000"), user=admin)
    assert exc.value.code == "wholesale_above_selling"


def _payload(code, wholesale):
    return {"code": code, "name": "Chair", "selling_price": "3000.00",
            "wholesale_price": wholesale, "category": Category.objects.first().pk,
            "unit": Unit.objects.first().pk}


@pytest.mark.django_db
def test_api_create_with_wholesale_and_change_it(client_for):
    client, _ = client_for("admin")

    created = client.post("/api/v1/products/", _payload("vc-020", "2700.00"), format="json")
    assert created.status_code == 201, created.data
    assert created.data["wholesale_price"] == "2700.00"
    product_url = f"/api/v1/products/{created.data['id']}/"

    bad = client.post("/api/v1/products/", _payload("vc-021", "3100.00"), format="json")
    assert bad.status_code == 400
    assert bad.data["code"] == "wholesale_above_selling"

    changed = client.post(product_url + "change-price/",
                          {"price_type": "wholesale", "new_price": "2650.00"}, format="json")
    assert changed.status_code == 200, changed.data
    assert changed.data["wholesale_price"] == "2650.00"

    patched = client.patch(product_url, {"wholesale_price": "1.00"}, format="json")
    assert patched.status_code == 200
    assert patched.data["wholesale_price"] == "2650.00"  # read-only on edit
