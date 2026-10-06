"""Any other text is a search (the requirement "Search"): `VC-001` shows the product card."""

from html import escape

from aiogram import F, Router
from aiogram.types import Message

from bot.api_client import ApiClient
from bot.keyboards import ALL_BUTTONS
from bot.texts import etb, product_card

router = Router(name="search")


@router.message(F.text, ~F.text.startswith("/"), ~F.text.in_(ALL_BUTTONS))
async def search(message: Message, api: ApiClient):
    found = await api.search(message.from_user.id, message.text)
    exact = found.get("exact")
    if exact and exact["kind"] != "product":
        await message.answer(f"🔎 {exact['kind'].replace('_', ' ')} "
                             f"<code>{escape(exact['number'])}</code> — open it on the web page "
                             "for the full history.")
        return
    replies = [product_card(row) for row in found["products"][:3]]
    replies += [f"👤 <b>{escape(c['name'])}</b> {escape(c['phone'] or '')} — owes "
                f"{etb(c['outstanding'])}" for c in found["customers"][:3]]
    replies += [f"🧾 <code>{o['number']}</code> {escape(o['customer'])} {etb(o['total'])} "
                f"({o['status'].replace('_', ' ')})" for o in found["orders"][:3]]
    if not replies:
        await message.answer("Nothing found. Try a product code like VC-001, a customer name "
                             "or a document number.")
        return
    for text in replies:
        await message.answer(text)
