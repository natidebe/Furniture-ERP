# Shared pytest fixtures for every app. factory_boy factories live in tests/factories.py.
import pytest
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _fast_password_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


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
