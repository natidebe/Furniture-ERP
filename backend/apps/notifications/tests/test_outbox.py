from datetime import timedelta

import httpx
import pytest
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import BusinessRuleError
from apps.notifications import tasks, telegram
from apps.notifications.models import NotificationOutbox
from apps.notifications.services import notify
from apps.requests import services as requests


@pytest.fixture
def linked(staff):
    """Give every staff member a Telegram id (their id + 1000)."""
    for user in vars(staff).values():
        user.telegram_id = 1000 + user.pk
        user.save(update_fields=["telegram_id"])
    return staff


def _request(staff, loc, product, qty=5):
    return requests.create_stock_request(requesting_location=loc.PIA, source_location=loc.PAW,
                                         lines=[{"product": product, "qty": qty}],
                                         salesperson=staff.sales)


@pytest.mark.django_db
def test_new_request_notifies_the_pawlos_storekeeper_with_buttons(linked, loc, product,
                                                                  stock):
    stock(product, loc.PAW, 10)

    request = _request(linked, loc, product)

    row = NotificationOutbox.objects.get(event_type="stock_request.created")
    assert row.target_user == linked.store
    assert row.chat_id == linked.store.telegram_id
    assert request.number in row.payload["text"] and "VC-001" in row.payload["text"]
    assert row.payload["buttons"][0][0]["callback_data"] == f"req:ack:{request.pk}"


@pytest.mark.django_db
def test_people_without_telegram_get_no_rows(staff, loc, product, stock):
    stock(product, loc.PAW, 10)
    _request(staff, loc, product)

    assert not NotificationOutbox.objects.exists()


@pytest.mark.django_db
def test_rolled_back_change_sends_nothing(linked, loc, product, stock):
    stock(product, loc.PAW, 10)

    with pytest.raises(RuntimeError), transaction.atomic():
        _request(linked, loc, product)
        raise RuntimeError("something later failed")

    assert not NotificationOutbox.objects.exists()


@pytest.mark.django_db
def test_failed_request_creation_sends_nothing(linked, loc, product, stock):
    stock(product, loc.PAW, 2)
    with pytest.raises(BusinessRuleError):
        _request(linked, loc, product, qty=5)

    assert not NotificationOutbox.objects.exists()


@pytest.mark.django_db
def test_release_notifies_salesperson_and_branch(linked, loc, product, stock):
    stock(product, loc.PAW, 10)
    request = _request(linked, loc, product)
    requests.acknowledge_request(request=request, user=linked.store)

    requests.release_stock(request=request, storekeeper=linked.store, destination_type="branch",
                           lines=[{"line_id": request.lines.get().pk, "qty": 5}])

    released = NotificationOutbox.objects.get(event_type="stock_request.released")
    assert released.target_user == linked.sales
    assert "TR-" in released.payload["text"]
    sent = NotificationOutbox.objects.filter(event_type="transfer.sent")
    assert set(sent.values_list("target_user", flat=True)) == {linked.sales.pk}  # PIA staff


@pytest.mark.django_db
def test_payment_to_verify_goes_to_accountants(linked, loc, goods, abc, accounts, stock):
    from apps.payments.services import record_payment

    linked.sales.allowed_payment_accounts.add(accounts.org)
    record_payment(customer=abc, account=accounts.org, amount="500", method="cash",
                   recorded_by=linked.sales)

    rows = NotificationOutbox.objects.filter(event_type="payment.to_verify")
    assert list(rows.values_list("target_user", flat=True)) == [linked.accountant.pk]
    assert rows.get().payload["buttons"][0][0]["callback_data"].startswith("pay:ok:")


# ---------------------------------------------------------------- sending

@pytest.fixture
def bot_token(settings):
    settings.TELEGRAM_BOT_TOKEN = "123:ABC"


def _queue(user, text="hello"):
    return NotificationOutbox.objects.create(event_type="test", target_user=user,
                                             chat_id=42, payload={"text": text, "buttons": []})


@pytest.mark.django_db
def test_sending_marks_rows_sent(bot_token, staff, monkeypatch):
    sent = []
    monkeypatch.setattr(tasks, "send", lambda chat_id, payload: sent.append((chat_id, payload)))
    row = _queue(staff.admin)

    assert tasks.send_pending_notifications() == 1

    row.refresh_from_db()
    assert (row.status, row.attempts) == ("sent", 0)
    assert sent == [(42, {"text": "hello", "buttons": []})]


@pytest.mark.django_db
def test_failures_retry_with_backoff_then_fail_after_five(bot_token, staff, monkeypatch):
    def broken(chat_id, payload):
        raise telegram.TelegramError("network: timeout")

    monkeypatch.setattr(tasks, "send", broken)
    row = _queue(staff.admin)
    delays = []
    for _ in range(5):
        NotificationOutbox.objects.filter(pk=row.pk).update(next_attempt_at=timezone.now())
        before = timezone.now()
        tasks.send_pending_notifications()
        row.refresh_from_db()
        delays.append(row.next_attempt_at - before)

    assert (row.status, row.attempts) == ("failed", 5)
    assert delays[0] >= timedelta(seconds=14) and delays[2] >= timedelta(seconds=59)


@pytest.mark.django_db
def test_permanent_errors_fail_at_once(bot_token, staff, monkeypatch):
    def blocked(chat_id, payload):
        raise telegram.TelegramError("403: bot was blocked by the user", permanent=True)

    monkeypatch.setattr(tasks, "send", blocked)
    row = _queue(staff.admin)

    tasks.send_pending_notifications()

    row.refresh_from_db()
    assert (row.status, row.attempts) == ("failed", 1)


@pytest.mark.django_db
def test_without_a_bot_token_nothing_is_sent_or_lost(settings, staff):
    settings.TELEGRAM_BOT_TOKEN = ""
    row = _queue(staff.admin)

    assert tasks.send_pending_notifications() == 0
    row.refresh_from_db()
    assert (row.status, row.attempts) == ("pending", 0)


def test_telegram_send_builds_the_bot_api_call(settings):
    settings.TELEGRAM_BOT_TOKEN = "123:ABC"
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    telegram.send(42, {"text": "<b>Hi</b>",
                       "buttons": [[{"text": "OK", "callback_data": "x"}]]}, client=client)

    assert str(calls[0].url) == "https://api.telegram.org/bot123:ABC/sendMessage"
    body = calls[0].read().decode()
    assert '"parse_mode":"HTML"' in body and '"inline_keyboard"' in body


def test_telegram_403_is_permanent_and_429_waits(settings):
    settings.TELEGRAM_BOT_TOKEN = "123:ABC"
    responses = iter([
        httpx.Response(403, json={"ok": False, "description": "Forbidden: bot was blocked"}),
        httpx.Response(429, json={"ok": False, "description": "Too Many Requests",
                                  "parameters": {"retry_after": 7}}),
    ])
    client = httpx.Client(transport=httpx.MockTransport(lambda request: next(responses)))

    with pytest.raises(telegram.TelegramError) as blocked:
        telegram.send(1, {"text": "x"}, client=client)
    with pytest.raises(telegram.TelegramError) as slow:
        telegram.send(1, {"text": "x"}, client=client)

    assert blocked.value.permanent
    assert not slow.value.permanent and slow.value.retry_after == 7


@pytest.mark.django_db
def test_notify_unknown_event_writes_nothing(staff):
    assert notify("nothing.happened", staff.admin) == 0
