import pytest


@pytest.mark.django_db
def test_health_returns_ok(client):
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_seed_demo_loads_users_stock_and_a_request(settings):
    from django.core.management import call_command

    from apps.accounts.models import User
    from apps.inventory.selectors import balance_mismatches
    from apps.requests.models import StockRequest

    settings.DEBUG = True
    call_command("seed_demo")
    call_command("seed_demo")  # rerun is harmless

    assert set(User.objects.values_list("role", flat=True)) == {
        "admin", "accountant", "salesperson", "storekeeper"}
    assert StockRequest.objects.count() == 1
    assert balance_mismatches() == []


@pytest.mark.django_db
def test_seed_demo_refuses_without_debug(settings):
    from django.core.management import CommandError, call_command

    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_demo")
