import pytest

from bot import keyboards as kb
from bot.flows import ReleaseDraft, parse_callback, parse_qty
from bot.texts import etb, product_card


def _request(status="acknowledged", customer=None):
    return {"id": 7, "number": "SR-2026-00007", "status": status, "customer": customer,
            "lines": [
                {"id": 1, "product_code": "VC-001", "product_name": "Visitor chair",
                 "qty_remaining": 20},
                {"id": 2, "product_code": "DS-003", "product_name": "Desk", "qty_remaining": 0},
                {"id": 3, "product_code": "CB-002", "product_name": "Cabinet",
                 "qty_remaining": 2},
            ]}


def test_release_flow_partial_to_branch():
    draft = ReleaseDraft.from_request(_request())
    assert [line["code"] for line in draft.lines] == ["VC-001", "CB-002"]  # open lines only

    draft.set_qty(15)
    draft.set_qty(0)  # skip the cabinet
    assert draft.lines_done
    draft.set_destination("branch")

    assert draft.payload() == {"destination_type": "branch",
                               "lines": [{"line_id": 1, "qty": 15}]}
    assert "15 × VC-001" in draft.summary()


def test_release_draft_survives_storage_round_trip():
    draft = ReleaseDraft.from_request(_request())
    draft.set_qty(3)

    again = ReleaseDraft.load(draft.dump())

    assert again.current["code"] == "CB-002" and again.chosen == {"1": 3}


def test_release_quantities_are_checked():
    draft = ReleaseDraft.from_request(_request())
    with pytest.raises(ValueError):
        draft.set_qty(21)
    with pytest.raises(ValueError):
        parse_qty("five", 20)
    with pytest.raises(ValueError):
        parse_qty("21", 20)
    assert parse_qty(" 4 ", 20) == 4


def test_pickup_needs_a_customer_and_something_chosen():
    draft = ReleaseDraft.from_request(_request())
    with pytest.raises(ValueError):
        draft.set_destination("customer_pickup")
    draft.set_qty(0)
    draft.set_qty(0)
    draft.set_destination("branch")
    with pytest.raises(ValueError, match="Nothing chosen"):
        draft.payload()

    with_customer = ReleaseDraft.from_request(_request(customer=5))
    with_customer.set_destination("customer_pickup")


@pytest.mark.parametrize("status", ["pending", "released", "rejected"])
def test_only_open_requests_can_be_released(status):
    with pytest.raises(ValueError):
        ReleaseDraft.from_request(_request(status=status))


def test_callbacks_and_menus():
    assert parse_callback("req:rel:12") == ("req", "rel", 12)
    with pytest.raises(ValueError):
        parse_callback("req:rel:x")

    store = kb.main_menu("storekeeper")
    assert [b.text for b in store.keyboard[0]] == [kb.STOCK_REQUESTS, kb.PAWLOS_STOCK]
    pending = kb.request_buttons({"id": 4, "status": "pending"})
    assert [b.callback_data for b in pending.inline_keyboard[0]] == ["req:ack:4", "req:rej:4"]
    assert kb.request_buttons({"id": 4, "status": "released"}) is None
    link = kb.inline([[("Open", "https://erp.example.com")]])
    assert link.inline_keyboard[0][0].url == "https://erp.example.com"


def test_product_card_matches_the_clients_example():
    card = product_card({"name": "Visitor chair", "code": "VC-001",
                         "selling_price": "2500.00", "wholesale_price": None,
                         "stock": {"PIA": 10, "DEN": 5, "PAW": 100, "TRANSIT": 0},
                         "in_transit": 0, "total": 115})
    assert card.splitlines() == ["<b>Visitor chair</b> — <code>VC-001</code>",
                                 "Price: 2,500 ETB", "PIA: 10", "DEN: 5", "PAW: 100",
                                 "<b>Total: 115</b>"]
    assert etb("1500.50") == "1,500.50 ETB"


def test_the_bot_assembles_with_every_router():
    from bot.config import load
    from bot.main import build_dispatcher

    dp = build_dispatcher(api=object(), cfg=load())

    names = [router.name for router in dp.sub_routers]
    assert names == ["start", "storekeeper", "salesperson", "accountant", "search"]
    assert names[-1] == "search"  # free-text search must come last
