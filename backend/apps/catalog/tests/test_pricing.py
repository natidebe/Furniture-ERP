from decimal import Decimal

import pytest

from apps.audit.models import AuditLog
from apps.catalog.models import PriceHistory
from apps.catalog.services import change_price
from apps.core.exceptions import BusinessRuleError
from tests.factories import ProductFactory


@pytest.mark.django_db
def test_change_price_writes_history_and_audit(make_user):
    admin = make_user(role="admin")
    product = ProductFactory(selling_price=Decimal("2500.00"))

    change_price(product=product, new_price=Decimal("2800.00"), user=admin, reason="New import")

    product.refresh_from_db()
    assert product.selling_price == Decimal("2800.00")
    history = PriceHistory.objects.get(product=product)
    assert (history.old_price, history.new_price) == (Decimal("2500.00"), Decimal("2800.00"))
    assert history.changed_by == admin
    log = AuditLog.objects.get(action="price_change", object_id=str(product.pk))
    assert log.model == "catalog.Product"
    assert log.before == {"price": "2500.00"}
    assert log.after == {"price": "2800.00"}
    assert log.reason == "New import"
    assert log.actor == admin


@pytest.mark.django_db
@pytest.mark.parametrize("price", ["0", "-5"])
def test_change_price_rejects_non_positive(make_user, price):
    product = ProductFactory()

    with pytest.raises(BusinessRuleError) as exc:
        change_price(product=product, new_price=Decimal(price), user=make_user(role="admin"))

    assert exc.value.code == "invalid_price"
    assert not PriceHistory.objects.exists()


@pytest.mark.django_db
def test_change_price_endpoint(client_for):
    client, _ = client_for("admin")
    product = ProductFactory(selling_price=Decimal("2500.00"))

    response = client.post(f"/api/v1/products/{product.id}/change-price/",
                           {"new_price": "2700.00", "reason": "Supplier increase"},
                           format="json")

    assert response.status_code == 200, response.data
    assert response.data["selling_price"] == "2700.00"
    history = client.get(f"/api/v1/products/{product.id}/price-history/")
    assert history.data[0]["new_price"] == "2700.00"


@pytest.mark.django_db
def test_change_price_to_same_value_returns_business_error(client_for):
    client, _ = client_for("admin")
    product = ProductFactory(selling_price=Decimal("2500.00"))

    response = client.post(f"/api/v1/products/{product.id}/change-price/",
                           {"new_price": "2500.00"}, format="json")

    assert response.status_code == 400
    assert response.data["code"] == "price_unchanged"
