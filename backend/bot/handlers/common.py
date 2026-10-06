from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from bot.api_client import ApiError
from bot.texts import NOT_LINKED


class ApiErrorMiddleware(BaseMiddleware):
    """Turn every API refusal into a plain reply, so the API's rules hold in the bot."""

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except ApiError as exc:
            text = NOT_LINKED if exc.not_linked else f"⚠️ {exc.detail}"
            if isinstance(event, CallbackQuery):
                await event.answer(exc.detail[:190], show_alert=True)
                if event.message:
                    await event.message.answer(text)
            elif isinstance(event, Message):
                await event.answer(text)
            return None
