"""Accountant (and admin): sales, payments to verify, credit, low stock, reports, Excel."""

from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot import keyboards as kb
from bot.api_client import ApiClient
from bot.flows import parse_callback
from bot.texts import etb, payment_card, sales_summary

router = Router(name="accountant")

TITLES = {"day": "Sales today", "week": "Sales this week", "month": "Sales this month",
          "year": "Sales this year"}


class RejectPayment(StatesGroup):
    reason = State()


@router.message(F.text == kb.SALES)
async def sales_today(message: Message, api: ApiClient):
    await message.answer(sales_summary("Sales today",
                                       await api.report(message.from_user.id, "sales")))


@router.message(F.text == kb.REPORTS)
async def reports(message: Message):
    await message.answer("Which period?", reply_markup=kb.REPORT_PERIODS)


@router.callback_query(F.data.startswith("rp:"))
async def report_period(call: CallbackQuery, api: ApiClient):
    period = call.data.split(":")[1]
    report = await api.report(call.from_user.id, "sales", period)
    await call.answer()
    await call.message.answer(sales_summary(TITLES.get(period, "Sales"), report))


@router.message(F.text == kb.EXPORT)
async def export(message: Message):
    await message.answer("Export sales to Excel for which period?",
                         reply_markup=kb.EXPORT_PERIODS)


@router.callback_query(F.data.startswith("rx:"))
async def export_period(call: CallbackQuery, api: ApiClient):
    period = call.data.split(":")[1]
    filename, content = await api.report_xlsx(call.from_user.id, "sales", period)
    await call.answer()
    await call.message.answer_document(BufferedInputFile(content, filename=filename))


@router.message(F.text == kb.CREDIT_REPORT)
async def credit(message: Message, api: ApiClient):
    report = await api.report(message.from_user.id, "credit", "day")
    rows = [f"{escape(c['customer'])}: {etb(c['outstanding'])}"
            + (f" (over 90 days: {etb(c['over_90'])})" if c["over_90"] != "0.00" else "")
            for c in report["customers"][:15]]
    await message.answer(f"📒 <b>Outstanding credit: {etb(report['outstanding_total'])}</b>\n"
                         + ("\n".join(rows) or "Nobody owes anything."))


@router.message(F.text == kb.STOCK)
async def low_stock(message: Message, api: ApiClient):
    rows = await api.low_stock(message.from_user.id)
    lines = [f"⚠️ <code>{escape(r['code'])}</code> {escape(r['name'])}: "
             f"{r['total_new']} (min {r['min_stock']})" for r in rows]
    await message.answer("📦 <b>Low stock</b>\n" + ("\n".join(lines) or "Nothing is low. 👍"))


@router.message(F.text == kb.PAYMENTS)
async def payments_to_verify(message: Message, api: ApiClient):
    payments = await api.unverified_payments(message.from_user.id)
    if not payments:
        await message.answer("No payments waiting. 👍")
    for p in payments[:10]:
        await message.answer(payment_card(p), reply_markup=kb.inline(
            [[("Verify", f"pay:ok:{p['id']}"), ("Reject", f"pay:rej:{p['id']}")]]))


@router.callback_query(F.data.startswith("pay:ok:"))
async def verify(call: CallbackQuery, api: ApiClient):
    _, _, payment_id = parse_callback(call.data)
    payment = await api.verify_payment(call.from_user.id, payment_id)
    await call.answer("Verified")
    await call.message.edit_text(payment_card(payment) + "\n✅ Verified")


@router.callback_query(F.data.startswith("pay:rej:"))
async def reject_start(call: CallbackQuery, state: FSMContext):
    _, _, payment_id = parse_callback(call.data)
    await state.set_state(RejectPayment.reason)
    await state.update_data(payment_id=payment_id)
    await call.answer()
    await call.message.answer("Why is it rejected? (e.g. not on the bank statement; or /cancel)")


@router.message(RejectPayment.reason)
async def reject_reason(message: Message, api: ApiClient, state: FSMContext):
    data = await state.get_data()
    payment = await api.reject_payment(message.from_user.id, data["payment_id"], message.text)
    await state.clear()
    await message.answer(f"❌ {payment['number']} rejected.")
