from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import TelegramLinkToken
from apps.accounts.services import create_link_code
from apps.accounts.tasks import expire_link_tokens
from apps.inventory import services
from apps.inventory.tasks import check_low_stock, nightly_stock_check
from apps.notifications.models import NotificationOutbox
from tests.factories import ProductFactory

TOKEN = "service-token-for-tests"


@pytest.fixture
def bot(settings, api_client):
    settings.BOT_SERVICE_TOKEN = TOKEN

    def as_telegram(telegram_id):
        api_client.credentials(HTTP_AUTHORIZATION=f"Bot {TOKEN}",
                               HTTP_X_TELEGRAM_USER=str(telegram_id), HTTP_X_CLIENT="bot")
        return api_client
    return as_telegram


# ---------------------------------------------------------------- linking and access

@pytest.mark.django_db
def test_start_code_links_telegram(bot, staff):
    code = create_link_code(user=staff.store).token

    response = bot(555).post("/api/v1/auth/telegram/link/", {"code": code.lower(),
                                                             "telegram_id": 555}, format="json")

    assert response.status_code == 200, response.data
    assert response.data["role"] == "storekeeper"
    staff.store.refresh_from_db()
    assert staff.store.telegram_id == 555
    assert TelegramLinkToken.objects.get(token=code).used_at is not None


@pytest.mark.django_db
def test_codes_are_single_use_and_expire(bot, staff):
    token = create_link_code(user=staff.store)
    bot(555).post("/api/v1/auth/telegram/link/", {"code": token.token, "telegram_id": 555},
                  format="json")
    again = bot(556).post("/api/v1/auth/telegram/link/", {"code": token.token,
                                                         "telegram_id": 556}, format="json")
    assert again.status_code == 400 and again.data["code"] == "invalid_code"

    old = create_link_code(user=staff.sales)
    TelegramLinkToken.objects.filter(pk=old.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1))
    expired = bot(557).post("/api/v1/auth/telegram/link/", {"code": old.token,
                                                           "telegram_id": 557}, format="json")
    assert expired.data["code"] == "invalid_code"


@pytest.mark.django_db
def test_one_telegram_account_per_user(bot, staff):
    staff.sales.telegram_id = 555
    staff.sales.save()
    code = create_link_code(user=staff.store).token

    response = bot(555).post("/api/v1/auth/telegram/link/", {"code": code, "telegram_id": 555},
                             format="json")

    assert response.data["code"] == "telegram_in_use"


@pytest.mark.django_db
def test_only_the_bot_can_link(api_client, staff, settings):
    settings.BOT_SERVICE_TOKEN = TOKEN
    code = create_link_code(user=staff.store).token
    api_client.credentials(HTTP_AUTHORIZATION="Bot wrong-token")

    response = api_client.post("/api/v1/auth/telegram/link/", {"code": code,
                                                              "telegram_id": 9}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_bot_acts_with_the_linked_users_own_permissions(bot, staff, loc, product, stock):
    from apps.requests.services import acknowledge_request, create_stock_request

    stock(product, loc.PAW, 10)
    request = create_stock_request(requesting_location=loc.PIA, source_location=loc.PAW,
                                   lines=[{"product": product, "qty": 2}],
                                   salesperson=staff.sales)
    acknowledge_request(request=request, user=staff.store)
    staff.sales.telegram_id, staff.store.telegram_id = 111, 222
    staff.sales.save()
    staff.store.save()
    body = {"destination_type": "branch",
            "lines": [{"line_id": request.lines.get().pk, "qty": 2}]}

    as_sales = bot(111).post(f"/api/v1/stock-requests/{request.pk}/release/", body,
                             format="json")
    assert as_sales.status_code == 403  # a salesperson cannot release, bot or not

    as_store = bot(222).post(f"/api/v1/stock-requests/{request.pk}/release/", body,
                             format="json")
    assert as_store.status_code == 201, as_store.data
    from apps.audit.models import AuditLog
    assert bot(222).get("/api/v1/auth/me/").data["username"] == staff.store.username
    assert not AuditLog.objects.filter(source="web", action__startswith="stock_request").exists()


@pytest.mark.django_db
def test_unlinked_telegram_gets_no_data(bot, staff):
    response = bot(999).get("/api/v1/stock/summary/")

    assert response.status_code == 401
    assert response.data["code"] == "not_linked"


@pytest.mark.django_db
def test_wrong_service_token_is_refused(api_client, staff, settings):
    settings.BOT_SERVICE_TOKEN = TOKEN
    staff.admin.telegram_id = 1
    staff.admin.save()
    api_client.credentials(HTTP_AUTHORIZATION="Bot guessed", HTTP_X_TELEGRAM_USER="1")

    assert api_client.get("/api/v1/auth/me/").status_code == 401


@pytest.mark.django_db
def test_bot_auth_is_off_when_no_service_token_is_configured(api_client, staff, settings):
    settings.BOT_SERVICE_TOKEN = ""
    staff.admin.telegram_id = 1
    staff.admin.save()
    api_client.credentials(HTTP_AUTHORIZATION="Bot ", HTTP_X_TELEGRAM_USER="1")

    assert api_client.get("/api/v1/auth/me/").status_code == 401


@pytest.mark.django_db
def test_user_can_unlink_own_telegram(client_for):
    client, user = client_for("salesperson")
    user.telegram_id = 77
    user.save()

    response = client.post("/api/v1/auth/telegram/unlink/")

    assert response.data["telegram_linked"] is False


@pytest.mark.django_db
def test_expired_link_codes_are_cleaned_up(staff):
    fresh = create_link_code(user=staff.sales)
    old = create_link_code(user=staff.store)
    TelegramLinkToken.objects.filter(pk=old.pk).update(
        expires_at=timezone.now() - timedelta(minutes=1))

    assert expire_link_tokens() == 1
    assert list(TelegramLinkToken.objects.values_list("pk", flat=True)) == [fresh.pk]


# ---------------------------------------------------------------- low stock and nightly check

@pytest.fixture
def linked_admin(staff):
    staff.admin.telegram_id = 1
    staff.admin.save()
    staff.store.telegram_id = 2
    staff.store.save()
    return staff


@pytest.mark.django_db
def test_low_stock_fires_below_minimum_once_a_day(linked_admin, loc, stock):
    chair = ProductFactory(code="OC-001", name="Office Chair A", min_stock=10)
    stock(chair, loc.PAW, 10)
    assert check_low_stock(chair.pk) is False  # 10 = 10: not low

    services.change_condition(product=chair, location=loc.PAW, qty=3, from_condition="new",
                              to_condition="damaged", user=linked_admin.admin, reason="Broken")
    assert check_low_stock(chair.pk) is True   # sellable 7 < 10
    assert check_low_stock(chair.pk) is False  # already alerted today

    rows = NotificationOutbox.objects.filter(event_type="stock.low")
    assert set(rows.values_list("target_user", flat=True)) == {linked_admin.admin.pk,
                                                               linked_admin.store.pk}
    text = rows.first().payload["text"]
    assert "LOW STOCK" in text and "Current stock: 7 pcs" in text and "Minimum: 10 pcs" in text


@pytest.mark.django_db
def test_stock_in_transit_counts_for_low_stock(linked_admin, loc, stock):
    chair = ProductFactory(code="OC-002", min_stock=10)
    stock(chair, loc.PAW, 10)
    services.create_transfer(from_location=loc.PAW, to_location=loc.PIA,
                             lines=[{"product": chair, "qty": 4}], user=linked_admin.admin)

    assert check_low_stock(chair.pk) is False


@pytest.mark.django_db
def test_nightly_check_alerts_admins_on_mismatch(linked_admin, loc, product, stock):
    from apps.inventory.models import StockBalance

    stock(product, loc.PAW, 5)
    assert nightly_stock_check() == 0
    StockBalance.objects.filter(product=product).update(on_hand=6)

    assert nightly_stock_check() == 1
    row = NotificationOutbox.objects.get(event_type="stock.mismatch")
    assert row.target_user == linked_admin.admin
