"""Entry point: `python -m bot.main`. Long polling when TELEGRAM_WEBHOOK_URL is empty
(development), otherwise an aiohttp webhook secured with the secret token (production)."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot import config as bot_config
from bot.api_client import ApiClient
from bot.handlers import accountant, salesperson, search, start, storekeeper
from bot.handlers.common import ApiErrorMiddleware

WEBHOOK_PATH = "/telegram/webhook"


def build_dispatcher(api: ApiClient, cfg: bot_config.Config) -> Dispatcher:
    storage = MemoryStorage()
    if cfg.redis_url:  # keeps half-finished flows across restarts
        from aiogram.fsm.storage.redis import RedisStorage

        storage = RedisStorage.from_url(cfg.redis_url)
    dp = Dispatcher(storage=storage, api=api, config=cfg)
    dp.message.middleware(ApiErrorMiddleware())
    dp.callback_query.middleware(ApiErrorMiddleware())
    # Order matters: free-text search is last.
    dp.include_routers(start.router, storekeeper.router, salesperson.router,
                       accountant.router, search.router)
    return dp


async def run() -> None:
    cfg = bot_config.load()
    if not cfg.bot_token or not cfg.service_token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and BOT_SERVICE_TOKEN.")
    bot = Bot(cfg.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    api = ApiClient(cfg.api_base_url, cfg.service_token)
    dp = build_dispatcher(api, cfg)
    try:
        if cfg.webhook_url:
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
            from aiohttp import web

            await bot.set_webhook(cfg.webhook_url.rstrip("/") + WEBHOOK_PATH,
                                  secret_token=cfg.webhook_secret or None,
                                  drop_pending_updates=False)
            app = web.Application()
            SimpleRequestHandler(dispatcher=dp, bot=bot,
                                 secret_token=cfg.webhook_secret or None).register(
                app, path=WEBHOOK_PATH)
            setup_application(app, dp, bot=bot)
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", cfg.port).start()
            await asyncio.Event().wait()
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)
    finally:
        await api.close()
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
