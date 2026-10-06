"""The bot's real API client against the real API (in-process, no network, no Telegram)."""

import httpx
import pytest
from django.core.asgi import get_asgi_application

from bot.api_client import ApiClient, ApiError
from bot.flows import ReleaseDraft

TOKEN = "bot-service-token"


@pytest.fixture
async def make_api(settings):
    from asgiref.sync import sync_to_async
    from django.db import connections

    settings.BOT_SERVICE_TOKEN = TOKEN
    # Django serves each request in its own thread; with persistent connections that
    # thread's connection would outlive the test and block dropping the test database.
    db_settings = connections.settings["default"]
    max_age = db_settings.get("CONN_MAX_AGE")
    db_settings["CONN_MAX_AGE"] = 0
    clients = []

    def _make(token=TOKEN):
        client = ApiClient("http://testserver/api/v1", token,
                           transport=httpx.ASGITransport(app=get_asgi_application()))
        clients.append(client)
        return client
    yield _make
    for client in clients:
        await client.close()
    # Django ran the views in its worker thread; close that thread's database connections
    # so the test database can be dropped afterwards.
    await sync_to_async(connections.close_all, thread_sensitive=True)()
    db_settings["CONN_MAX_AGE"] = max_age


@pytest.fixture
def linked(staff):
    staff.sales.telegram_id, staff.store.telegram_id = 111, 222
    staff.sales.save()
    staff.store.save()
    return staff


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
async def test_storekeeper_releases_entirely_from_the_bot(make_api, linked, loc, product,
                                                         stock):
    """Phase 4 definition of done: a request card → acknowledge → release, all via the bot."""
    from asgiref.sync import sync_to_async

    await sync_to_async(stock)(product, loc.PAW, 30)
    api = make_api()
    created = await api.create_request(111, product.pk, 12, reference="Bot test")
    assert created["number"].startswith("SR-")

    queue = await api.stock_requests(222, "pending")
    assert [r["number"] for r in queue] == [created["number"]]

    acknowledged = await api.acknowledge(222, created["id"])
    draft = ReleaseDraft.from_request(acknowledged)
    draft.set_qty(10)
    draft.set_destination("branch")
    release = await api.release(222, created["id"], draft.payload())

    assert release["number"].startswith("SRL-") and release["transfer_number"]
    after = await api.stock_request(222, created["id"])
    assert after["status"] == "partially_released"
    assert after["lines"][0]["qty_remaining"] == 2


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
async def test_bot_errors_carry_the_api_code(make_api, linked, loc, product, stock):
    from asgiref.sync import sync_to_async

    await sync_to_async(stock)(product, loc.PAW, 5)
    api = make_api()
    created = await api.create_request(111, product.pk, 2)

    with pytest.raises(ApiError) as permission:  # a salesperson cannot acknowledge
        await api.acknowledge(111, created["id"])
    assert permission.value.status == 403

    with pytest.raises(ApiError) as state:  # release before acknowledge
        await api.release(222, created["id"], {"destination_type": "branch",
                                               "lines": [{"line_id": 1, "qty": 1}]})
    assert state.value.code == "invalid_state"

    with pytest.raises(ApiError) as unlinked:
        await api.me(999)
    assert unlinked.value.not_linked

    with pytest.raises(ApiError) as bad_token:
        await make_api(token="wrong").me(222)
    assert bad_token.value.status == 401


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
async def test_link_and_search_from_the_bot(make_api, staff, loc, product, stock):
    from asgiref.sync import sync_to_async

    from apps.accounts.services import create_link_code

    await sync_to_async(stock)(product, loc.PAW, 7)
    code = (await sync_to_async(create_link_code)(user=staff.sales)).token
    api = make_api()

    me = await api.link(code, 333)
    assert me["role"] == "salesperson"
    found = await api.search(333, "vc-001")
    assert found["exact"]["kind"] == "product"
    assert found["products"][0]["stock"]["PAW"] == 7
    filename, content = None, None
    with pytest.raises(ApiError):  # salespeople have no Excel export
        filename, content = await api.report_xlsx(333, "sales", "day")
    assert filename is None and content is None
