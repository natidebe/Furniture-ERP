from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.payments.models import PaymentAccount
from tests.factories import CustomerFactory, ProductFactory


@pytest.fixture
def accounts(db):
    return SimpleNamespace(
        org=PaymentAccount.objects.create(name="CBE – Company", kind="organization",
                                          method="bank"),
        personal=PaymentAccount.objects.create(name="Telebirr – Owner", kind="personal",
                                               method="mobile_money"),
    )


@pytest.fixture
def goods(db):
    return SimpleNamespace(
        chair=ProductFactory(code="VC-001", name="Visitor chair", selling_price=Decimal("5000"),
                             wholesale_price=Decimal("4500")),
        desk=ProductFactory(code="DS-003", name="Manager desk", selling_price=Decimal("20000")),
        cabinet=ProductFactory(code="CB-002", name="Cabinet", selling_price=Decimal("20000")),
    )


@pytest.fixture
def abc(db):
    return CustomerFactory(name="ABC Furniture", type="reseller", credit_allowed=True)


@pytest.fixture
def walk_in(db):
    from apps.customers.models import Customer

    return Customer.objects.get(name="Walk-in Customer")
