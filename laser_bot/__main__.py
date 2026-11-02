"""Запуск: python -m laser_bot"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from . import config, db
from .handlers import admin, client
from .reminders import reminder_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not config.BOT_TOKEN:
        sys.exit("Не задано BOT_TOKEN. Створіть файл laser_bot/.env (див. .env.example).")
    if not config.ADMIN_IDS:
        logging.warning("ADMIN_IDS не задано: сповіщення про записи нікому не надходитимуть.")

    await db.init()
    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(admin.router)   # адмін-команди мають пріоритет
    dp.include_router(client.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Головне меню"),
        BotCommand(command="book", description="Записатися"),
        BotCommand(command="prices", description="Ціни"),
        BotCommand(command="my", description="Мої записи"),
    ])
    reminders = asyncio.create_task(reminder_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        reminders.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
