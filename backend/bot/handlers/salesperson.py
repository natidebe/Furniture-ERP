"""Salesperson: check stock, request stock, customers, my orders, my sales, incoming
transfers. New sales are entered on the web page (D10)."""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot.api_client import ApiClient
from bot.flows import parse_callback
from bot.texts import etb, order_line, product_card, sales_summary

router = Router(name="salesperson")


class Ask(StatesGroup):
    product = State()
    customer = State()
    request_product = State()
    request_qty = State()
    request_confirm = State()


@router.message(F.text == kb.NEW_SALE)
async def new_sale(message: Message, config):
    if config.web_app_url:
        await message.answer("New sales and payments are entered on the web page.",
                             reply_markup=kb.inline([[("Open the web app",
                                                       config.web_app_url)]]))
    else:
        await message.answer("New sales and payments are entered on the web page.")


@router.message(F.text == kb.CHECK_STOCK)
async def check_stock(message: Message, state: FSMContext):
    await state.set_state(Ask.product)
    await message.answer("Type a product code or name (e.g. VC-001).")


@router.message(Ask.product)
async def check_stock_answer(message: Message, api: ApiClient, state: FSMContext):
    await state.clear()
    found = await api.search(message.from_user.id, message.text)
    if not found["products"]:
        await message.answer("No product found.")
        return
    for row in found["products"][:3]:
        await message.answer(product_card(row))


@router.message(F.text.in_({kb.CUSTOMERS, kb.CREDIT}))
async def customers(message: Message, state: FSMContext):
    await state.set_state(Ask.customer)
    await message.answer("Type the customer's name, shop or phone.")


@router.message(Ask.customer)
async def customers_answer(message: Message, api: ApiClient, state: FSMContext):
    await state.clear()
    found = await api.search(message.from_user.id, message.text)
    if not found["customers"]:
        await message.answer("No customer found.")
        return
    await message.answer("\n".join(
        f"👤 <b>{escape(c['name'])}</b>"
        + (f" — {escape(c['shop_name'])}" if c["shop_name"] else "")
        + f"\n{escape(c['phone'] or '')} {escape(c['city'] or '')}\nOwes: {etb(c['outstanding'])}"
        for c in found["customers"][:5]))


@router.message(F.text == kb.MY_ORDERS)
async def my_orders(message: Message, api: ApiClient):
    orders = await api.my_orders(message.from_user.id)
    await message.answer("📋 <b>Latest sales</b>\n"
                         + ("\n".join(order_line(o) for o in orders) or "None yet."))


@router.message(F.text == kb.MY_SALES)
async def my_sales(message: Message, api: ApiClient):
    report = await api.report(message.from_user.id, "sales", "day")
    await message.answer(sales_summary("My sales today", report))


@router.message(F.text == kb.INCOMING)
async def incoming(message: Message, api: ApiClient):
    me = await api.me(message.from_user.id)
    if not me.get("home_location"):
        await message.answer("You have no home location; ask the admin.")
        return
    transfers = await api.transfers_in_transit(message.from_user.id, me["home_location"])
    if not transfers:
        await message.answer("Nothing on its way to you.")
    for t in transfers:
        items = "\n".join(f"• {ln['qty_sent']} × {escape(ln['product_code'])}"
                          for ln in t["lines"])
        await message.answer(f"🚚 <code>{t['number']}</code> from {t['from_location_code']}\n"
                             f"{items}",
                             reply_markup=kb.inline([[("Received everything",
                                                       f"tr:recv:{t['id']}")]]))


@router.callback_query(F.data.startswith("tr:recv:"))
async def receive(call: CallbackQuery, api: ApiClient):
    _, _, transfer_id = parse_callback(call.data)
    transfer = await api.receive_transfer(call.from_user.id, transfer_id)
    await call.answer("Received")
    await call.message.edit_text(f"✅ <code>{transfer['number']}</code> received in full. "
                                 "(If something is missing, receive it on the web page "
                                 "instead.)")


# ---------------------------------------------------------------- simple stock request

@router.message(F.text == kb.REQUEST_STOCK)
async def request_start(message: Message, state: FSMContext):
    await state.set_state(Ask.request_product)
    await message.answer("Which product? Type its code (e.g. VC-001).")


@router.message(Ask.request_product)
async def request_product(message: Message, api: ApiClient, state: FSMContext):
    found = await api.search(message.from_user.id, message.text)
    exact = found.get("exact")
    product = (next((p for p in found["products"] if p["id"] == exact["id"]), None)
               if exact and exact["kind"] == "product" else None)
    if product is None:
        await message.answer("Type the exact product code (e.g. VC-001), or /cancel.")
        return
    await state.update_data(product=product)
    await state.set_state(Ask.request_qty)
    await message.answer(product_card(product) + "\n\nHow many do you need from Pawlos?")


@router.message(Ask.request_qty)
async def request_qty(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("Type a whole number above 0, or /cancel.")
        return
    data = await state.get_data()
    await state.update_data(qty=int(text))
    await state.set_state(Ask.request_confirm)
    await message.answer(f"Request {int(text)} × <code>{escape(data['product']['code'])}</code> "
                         f"from Pawlos for your branch?", reply_markup=kb.CONFIRM)


@router.callback_query(Ask.request_confirm, F.data.startswith("rc:"))
async def request_confirm(call: CallbackQuery, api: ApiClient, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    if call.data != "rc:yes":
        await call.answer("Cancelled")
        return
    request = await api.create_request(call.from_user.id, data["product"]["id"], data["qty"])
    await call.answer("Sent")
    await call.message.answer(f"✅ Request <code>{request['number']}</code> sent to Pawlos.")
