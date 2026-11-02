"""Фонові нагадування клієнтам за 24 і 2 години до візиту."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from . import config, db, texts

log = logging.getLogger(__name__)


async def send_due(bot: Bot) -> None:
    now = datetime.now(config.TZ)
    for hours, intro in ((24, "Нагадуємо: завтра у вас запис 💫"),
                         (2, "Чекаємо на вас уже скоро! ⏰")):
        for b in await db.due_reminders(now, hours):
            text = f"{intro}\n\n{texts.booking_card(b)}\n\n📍 {escape(config.SALON_ADDRESS)}"
            if hours == 24:
                text += f"\n\n{config.PREPARATION_TIPS}"
            try:
                await bot.send_message(b.user_id, text)
            except TelegramAPIError as e:
                log.warning("Нагадування #%s не надіслано: %s", b.id, e)
            await db.mark_reminded(b.id, hours)


async def reminder_loop(bot: Bot, interval: int = 60) -> None:
    while True:
        try:
            await send_due(bot)
        except Exception:
            log.exception("Помилка у циклі нагадувань")
        await asyncio.sleep(interval)
