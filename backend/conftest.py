# Shared pytest fixtures for every app. factory_boy factories live in tests/factories.py.
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from config.celery import app as celery_app
from tests.factories import ProductFactory, UserFactory


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True, scope="session")
def _celery_runs_inline():
    """Tasks run in-process, so tests never need Redis."""
    celery_app.conf.task_always_eager = True


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def make_user(db):
    """make_user(role="accountant", **fields) → a saved user."""
    return UserFactory


@pytest.fixture
def client_for(api_client, make_user):
    """client_for("salesperson") → (APIClient authenticated as a new user of that role, user)."""

    def _client_for(role, **fields):
        user = make_user(role=role, **fields)
        api_client.force_authenticate(user)
        return api_client, user

    return _client_for


@pytest.fixture
def loc(db):
    """The seeded locations by code: loc.PIA, loc.PIA_UG, loc.DEN, loc.PAW, loc.TRANSIT."""
    from apps.locations.models import Location

    return SimpleNamespace(**{x.code.replace("-", "_"): x for x in Location.objects.all()})


@pytest.fixture
def staff(make_user, loc):
    """One user per role, with the usual home locations."""
    return SimpleNamespace(
        sales=make_user(role="salesperson", home_location=loc.PIA),
        den_sales=make_user(role="salesperson", home_location=loc.DEN),
        store=make_user(role="storekeeper", home_location=loc.PAW),
        accountant=make_user(role="accountant"),
        admin=make_user(role="admin"),
    )


@pytest.fixture
def stock(staff):
    """stock(product, location, qty) → receive qty into location (as the admin)."""
    from apps.inventory.services import receive_goods

    def _stock(product, location, qty):
        return receive_goods(location=location, lines=[{"product": product, "qty": qty}],
                             user=staff.admin, reference="test stock")

    return _stock


@pytest.fixture
def product(db):
    return ProductFactory(code="VC-001", name="Visitor chair")


def on_hand(product, location) -> tuple[int, int]:
    """(on_hand, reserved) for a product at a location; (0, 0) when there is no row."""
    from apps.inventory.models import StockBalance

    bal = StockBalance.objects.filter(product=product, location=location).first()
    return (bal.on_hand, bal.reserved) if bal else (0, 0)


@pytest.fixture
def balance():
    return on_hand
