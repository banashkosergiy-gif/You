"""Команди адміністратора (майстра)."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .. import config, db, texts
from ..slots import day_bounds, fmt_day

log = logging.getLogger(__name__)
router = Router(name="admin")
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(config.ADMIN_IDS))

HELP = (
    "🛠 <b>Команди адміністратора</b>\n\n"
    "/today — записи на сьогодні\n"
    "/tomorrow — записи на завтра\n"
    "/week — записи на 7 днів\n"
    "/day 05.11 — записи на дату\n"
    "/block 05.11 — закрити день для запису\n"
    "/unblock 05.11 — відкрити день\n"
    "/blocked — список закритих днів\n\n"
    "Про нові записи та скасування бот повідомляє автоматично."
)


def today() -> date:
    return datetime.now(config.TZ).date()


def parse_day(arg: str | None) -> date | None:
    """Приймає 05.11, 05.11.2026 або 2026-11-05."""
    if not arg:
        return None
    arg = arg.strip()
    try:
        if "-" in arg:
            return date.fromisoformat(arg)
        parts = [int(x) for x in arg.split(".")]
        if len(parts) == 3:
            return date(parts[2], parts[1], parts[0])
        if len(parts) == 2:
            d = date(today().year, parts[1], parts[0])
            return d if d >= today() else d.replace(year=d.year + 1)
    except ValueError:
        return None
    return None


async def send_range(message: Message, first: date, days: int) -> None:
    start = day_bounds(first)[0]
    end = day_bounds(first + timedelta(days=days - 1))[0] + timedelta(days=1)
    items = await db.bookings_between(start, end)
    title = fmt_day(first) if days == 1 else \
        f"{fmt_day(first)} – {fmt_day(first + timedelta(days=days - 1))}"
    if not items:
        await message.answer(f"📭 {title}: записів немає.")
        return
    total = sum(b.price for b in items)
    lines = [f"📋 <b>{title}</b> — {len(items)} зап., {total} {config.CURRENCY}"]
    current_day = None
    for b in items:
        if days > 1 and b.start.date() != current_day:
            current_day = b.start.date()
            lines.append(f"\n<b>{fmt_day(current_day)}</b>")
        lines.append("\n" + texts.booking_card(b, with_client=True))
    kb = InlineKeyboardBuilder()
    for b in items:
        kb.button(text=f"❌ #{b.id} {b.start:%d.%m %H:%M}", callback_data=f"admcancel:{b.id}")
    kb.adjust(2)
    await message.answer("\n".join(lines), reply_markup=kb.as_markup())


@router.message(Command("admin", "help"))
async def admin_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    await send_range(message, today(), 1)


@router.message(Command("tomorrow"))
async def cmd_tomorrow(message: Message) -> None:
    await send_range(message, today() + timedelta(days=1), 1)


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    await send_range(message, today(), 7)


@router.message(Command("day"))
async def cmd_day(message: Message, command: CommandObject) -> None:
    d = parse_day(command.args)
    if not d:
        await message.answer("Вкажіть дату: /day 05.11")
        return
    await send_range(message, d, 1)


@router.message(Command("block"))
async def cmd_block(message: Message, command: CommandObject) -> None:
    d = parse_day(command.args)
    if not d:
        await message.answer("Вкажіть дату: /block 05.11")
        return
    await db.block_day(d)
    existing = await db.bookings_between(*day_bounds(d))
    note = (f"\n⚠️ На цей день уже є записи ({len(existing)}): вони не скасовані, "
            f"перегляньте їх через /day {d:%d.%m}") if existing else ""
    await message.answer(f"🔒 {fmt_day(d)} закрито для нових записів.{note}")


@router.message(Command("unblock"))
async def cmd_unblock(message: Message, command: CommandObject) -> None:
    d = parse_day(command.args)
    if not d:
        await message.answer("Вкажіть дату: /unblock 05.11")
        return
    if await db.unblock_day(d):
        await message.answer(f"🔓 {fmt_day(d)} знову відкрито для запису.")
    else:
        await message.answer(f"{fmt_day(d)} і так не був закритий.")


@router.message(Command("blocked"))
async def cmd_blocked(message: Message) -> None:
    days = sorted(d for d in await db.blocked_days() if d >= today())
    if not days:
        await message.answer("Закритих днів немає.")
        return
    await message.answer("🔒 Закриті дні:\n" + "\n".join(f"• {fmt_day(d)}" for d in days))


@router.callback_query(F.data.startswith("admcancel:"))
async def adm_cancel_ask(call: CallbackQuery) -> None:
    booking_id = int(call.data.split(":")[1])
    b = await db.get_booking(booking_id)
    if not b or b.status != "active":
        await call.answer("Запис уже скасовано", show_alert=True)
        return
    await call.message.answer(
        f"Скасувати запис і повідомити клієнта?\n\n{texts.booking_card(b, with_client=True)}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Так, скасувати", callback_data=f"admcancel_yes:{b.id}"),
            InlineKeyboardButton(text="Ні", callback_data="admcancel_no"),
        ]]))
    await call.answer()


@router.callback_query(F.data == "admcancel_no")
async def adm_cancel_no(call: CallbackQuery) -> None:
    await call.message.delete()
    await call.answer()


@router.callback_query(F.data.startswith("admcancel_yes:"))
async def adm_cancel_yes(call: CallbackQuery, bot: Bot) -> None:
    booking_id = int(call.data.split(":")[1])
    b = await db.get_booking(booking_id)
    if not b or not await db.cancel_booking(booking_id):
        await call.answer("Запис уже скасовано", show_alert=True)
        return
    await call.message.edit_text(f"❌ Скасовано\n\n{texts.booking_card(b, with_client=True)}")
    await call.answer("Скасовано")
    try:
        await bot.send_message(
            b.user_id,
            f"😔 На жаль, ваш запис скасовано салоном.\n\n{texts.booking_card(b)}\n\n"
            f"Оберіть інший час через меню або зателефонуйте: {config.SALON_PHONE}")
    except TelegramAPIError as e:
        log.warning("Не вдалося повідомити клієнта %s: %s", b.user_id, e)
