from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from bot.api_client import ApiClient, ApiError
from bot.keyboards import main_menu
from bot.texts import NOT_LINKED

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, api: ApiClient, state: FSMContext):
    """/start CODE links this Telegram account; /start alone shows the menu."""
    await state.clear()
    code = (command.args or "").strip()
    if code:
        user = await api.link(code, message.from_user.id)
        await message.answer(f"✅ Linked to <b>{escape(user['name'])}</b> ({user['role']}).",
                             reply_markup=main_menu(user["role"]))
        return
    await show_menu(message, api)


@router.message(Command("menu"))
async def menu(message: Message, api: ApiClient, state: FSMContext):
    await state.clear()
    await show_menu(message, api)


@router.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.")


async def show_menu(message: Message, api: ApiClient):
    try:
        me = await api.me(message.from_user.id)
    except ApiError as exc:
        if exc.not_linked:
            await message.answer(NOT_LINKED, reply_markup=ReplyKeyboardRemove())
            return
        raise
    await message.answer(f"🏠 Main menu — {escape(me['name'])}",
                         reply_markup=main_menu(me["role"]))
