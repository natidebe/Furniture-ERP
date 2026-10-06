"""Storekeeper: requests list, acknowledge, reject and the release flow (BUILD_PHASES 4.2)."""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot.api_client import ApiClient
from bot.flows import ReleaseDraft, parse_callback, parse_qty
from bot.texts import request_card

router = Router(name="storekeeper")


class Release(StatesGroup):
    qty = State()
    destination = State()
    confirm = State()


class RejectRequest(StatesGroup):
    reason = State()


async def _send_requests(message: Message, api: ApiClient, statuses: list[str]):
    shown = 0
    for status in statuses:
        for request in await api.stock_requests(message.from_user.id, status):
            await message.answer(request_card(request), reply_markup=kb.request_buttons(request))
            shown += 1
            if shown >= 10:
                return
    if not shown:
        await message.answer("No open requests. 👍")


@router.message(F.text == kb.STOCK_REQUESTS)
async def list_requests(message: Message, api: ApiClient):
    await _send_requests(message, api, ["pending", "acknowledged", "partially_released"])


@router.message(F.text == kb.RELEASE_STOCK)
async def list_releasable(message: Message, api: ApiClient):
    await _send_requests(message, api, ["acknowledged", "partially_released"])


@router.message(F.text == kb.PAWLOS_STOCK)
async def warehouse_stock(message: Message, api: ApiClient):
    me = await api.me(message.from_user.id)
    if not me.get("home_location"):
        await message.answer("You have no home location; ask the admin.")
        return
    rows = await api.balances(message.from_user.id, me["home_location"])
    lines = [f"<code>{escape(r['product_code'])}</code> {r['on_hand']} "
             f"(free {r['available']}"
             + (f", display {r['display']}" if r["display"] else "")
             + (f", damaged {r['damaged']}" if r["damaged"] else "") + ")"
             for r in rows if r["on_hand"]]
    await message.answer("🏭 <b>Stock here</b>\n" + ("\n".join(lines[:40]) or "Empty."))


@router.message(F.text == kb.STOCK_HISTORY)
async def history(message: Message, api: ApiClient):
    me = await api.me(message.from_user.id)
    rows = await api.movements(message.from_user.id, me.get("home_location"))
    lines = [f"{m['occurred_at'][:16].replace('T', ' ')} {m['type']} {m['qty']} × "
             f"<code>{escape(m['product_code'])}</code> "
             f"{m['from_location_code'] or '—'}→{m['to_location_code'] or 'customer'}"
             for m in rows]
    await message.answer("📋 <b>Latest movements</b>\n" + ("\n".join(lines) or "None yet."))


# ---------------------------------------------------------------- acknowledge / reject

@router.callback_query(F.data.startswith("req:ack:"))
async def acknowledge(call: CallbackQuery, api: ApiClient):
    _, _, request_id = parse_callback(call.data)
    request = await api.acknowledge(call.from_user.id, request_id)
    await call.message.edit_text(request_card(request), reply_markup=kb.request_buttons(request))
    await call.answer("Acknowledged")


@router.callback_query(F.data.startswith("req:rej:"))
async def reject_start(call: CallbackQuery, state: FSMContext):
    _, _, request_id = parse_callback(call.data)
    await state.set_state(RejectRequest.reason)
    await state.update_data(request_id=request_id)
    await call.message.answer("Why are you rejecting it? (or /cancel)")
    await call.answer()


@router.message(RejectRequest.reason)
async def reject_reason(message: Message, api: ApiClient, state: FSMContext):
    data = await state.get_data()
    request = await api.reject_request(message.from_user.id, data["request_id"], message.text)
    await state.clear()
    await message.answer(f"❌ {request['number']} rejected; the reserved stock is free again.")


# ---------------------------------------------------------------- release flow

async def _ask_next(target: Message, draft: ReleaseDraft, state: FSMContext):
    if not draft.lines_done:
        line = draft.current
        await state.set_state(Release.qty)
        await target.answer(f"How many <code>{escape(line['code'])}</code> "
                            f"{escape(line['name'])} did you take out? "
                            f"(0–{line['remaining']}; type a number or tap)",
                            reply_markup=kb.qty_buttons(line))
    else:
        await state.set_state(Release.destination)
        await target.answer("Where do they go?",
                            reply_markup=kb.destination_buttons(draft.has_customer))
    await state.update_data(draft=draft.dump())


@router.callback_query(F.data.startswith("req:rel:"))
async def release_start(call: CallbackQuery, api: ApiClient, state: FSMContext):
    _, _, request_id = parse_callback(call.data)
    request = await api.stock_request(call.from_user.id, request_id)
    try:
        draft = ReleaseDraft.from_request(request)
    except ValueError as exc:
        await call.answer(str(exc), show_alert=True)
        return
    await call.answer()
    await call.message.answer(f"🚚 Releasing <code>{draft.number}</code>")
    await _ask_next(call.message, draft, state)


async def _take_qty(target: Message, qty_text: str, state: FSMContext):
    draft = ReleaseDraft.load((await state.get_data())["draft"])
    try:
        draft.set_qty(parse_qty(qty_text, draft.current["remaining"]))
    except ValueError as exc:
        await target.answer(f"⚠️ {exc}")
        return
    await _ask_next(target, draft, state)


@router.callback_query(Release.qty, F.data.startswith("rq:"))
async def release_qty_button(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await _take_qty(call.message, call.data.split(":")[1], state)


@router.message(Release.qty)
async def release_qty_typed(message: Message, state: FSMContext):
    await _take_qty(message, message.text, state)


@router.callback_query(Release.destination, F.data.startswith("rd:"))
async def release_destination(call: CallbackQuery, state: FSMContext):
    draft = ReleaseDraft.load((await state.get_data())["draft"])
    try:
        draft.set_destination(call.data.split(":")[1])
        draft.payload()
    except ValueError as exc:
        await call.answer(str(exc), show_alert=True)
        if "Nothing chosen" in str(exc):
            await state.clear()
        return
    await call.answer()
    await state.set_state(Release.confirm)
    await state.update_data(draft=draft.dump())
    await call.message.answer(escape(draft.summary()), reply_markup=kb.CONFIRM)


@router.callback_query(Release.confirm, F.data.startswith("rc:"))
async def release_confirm(call: CallbackQuery, api: ApiClient, state: FSMContext):
    draft = ReleaseDraft.load((await state.get_data())["draft"])
    await state.clear()
    if call.data != "rc:yes":
        await call.answer("Cancelled")
        await call.message.answer("Release cancelled; nothing changed.")
        return
    release = await api.release(call.from_user.id, draft.request_id, draft.payload())
    await call.answer("Released")
    text = f"✅ Released: <code>{release['number']}</code>"
    if release.get("transfer_number"):
        text += f"\nTransfer <code>{release['transfer_number']}</code> is on its way."
    await call.message.answer(text)
