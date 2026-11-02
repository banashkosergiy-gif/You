"""Сценарій клієнта: прайс, запис, мої записи."""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from .. import config, db, keyboards as kb, texts
from ..slots import candidate_days, day_bounds, fmt_day, fmt_duration, free_slots

log = logging.getLogger(__name__)
router = Router(name="client")


class Booking(StatesGroup):
    procedures = State()
    day = State()
    time = State()
    name = State()
    phone = State()
    confirm = State()


def now() -> datetime:
    return datetime.now(config.TZ)


def _summary(data: dict) -> tuple[list[config.Procedure], int, int]:
    chosen = [config.PROCEDURES_BY_ID[i] for i in data.get("selected", [])
              if i in config.PROCEDURES_BY_ID]
    return chosen, sum(p.price for p in chosen), sum(p.duration for p in chosen)


async def notify_admins(bot: Bot, text: str, **kwargs) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, **kwargs)
        except TelegramAPIError as e:
            log.warning("Не вдалося надіслати адміну %s: %s", admin_id, e)


async def _edit(call: CallbackQuery, text: str, markup=None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:  # повідомлення не змінилося або застаріло
        await call.message.answer(text, reply_markup=markup)


# ----------------------------------------------------------- головне меню --

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"Вітаємо в <b>{escape(config.SALON_NAME)}</b>! ✨\n\n"
        "Тут можна переглянути ціни на лазерну епіляцію "
        "та записатися на зручний час.",
        reply_markup=kb.main_menu())


@router.message(Command("myid"))
async def my_id(message: Message) -> None:
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


@router.message(F.text == kb.BTN_PRICES)
@router.message(Command("prices"))
async def prices(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.price_list(), reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_CONTACTS)
async def contacts(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.contacts(), reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_MY)
@router.message(Command("my"))
async def my_bookings(message: Message, state: FSMContext) -> None:
    await state.clear()
    items = await db.user_upcoming(message.from_user.id, now())
    if not items:
        await message.answer("У вас немає майбутніх записів.", reply_markup=kb.main_menu())
        return
    await message.answer("Ваші майбутні записи:", reply_markup=kb.main_menu())
    for b in items:
        await message.answer(texts.booking_card(b), reply_markup=kb.my_booking(b.id))


@router.callback_query(F.data.startswith("mycancel:"))
async def my_cancel_ask(call: CallbackQuery) -> None:
    booking_id = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(reply_markup=kb.my_booking_confirm(booking_id))
    await call.answer("Точно скасувати?")


@router.callback_query(F.data.startswith("mycancel_no:"))
async def my_cancel_no(call: CallbackQuery) -> None:
    booking_id = int(call.data.split(":")[1])
    await call.message.edit_reply_markup(reply_markup=kb.my_booking(booking_id))
    await call.answer("Запис залишається в силі")


@router.callback_query(F.data.startswith("mycancel_yes:"))
async def my_cancel_yes(call: CallbackQuery, bot: Bot) -> None:
    booking_id = int(call.data.split(":")[1])
    b = await db.get_booking(booking_id)
    if not b or b.user_id != call.from_user.id or b.status != "active":
        await call.answer("Запис не знайдено або вже скасовано", show_alert=True)
        return
    await db.cancel_booking(booking_id)
    await call.message.edit_text(f"❌ Скасовано\n\n{texts.booking_card(b)}")
    await call.answer("Запис скасовано")
    await notify_admins(bot, f"❌ <b>Клієнт скасував запис</b>\n\n"
                             f"{texts.booking_card(b, with_client=True)}")


# ---------------------------------------------------------------- запис ----

@router.message(F.text == kb.BTN_BOOK)
@router.message(Command("book"))
async def book_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Booking.procedures)
    await state.update_data(selected=[])
    await message.answer("Оберіть одну або кілька зон 👇", reply_markup=kb.procedures([]))


@router.callback_query(Booking.procedures, F.data.startswith("proc:"))
async def toggle_procedure(call: CallbackQuery, state: FSMContext) -> None:
    proc_id = call.data.split(":", 1)[1]
    data = await state.get_data()
    selected: list[str] = data.get("selected", [])
    if proc_id == "done":
        if not selected:
            await call.answer("Оберіть хоча б одну зону", show_alert=True)
            return
        await show_days(call, state)
        return
    if proc_id not in config.PROCEDURES_BY_ID:
        await call.answer()
        return
    if proc_id in selected:
        selected.remove(proc_id)
    else:
        selected.append(proc_id)
    await state.update_data(selected=selected)
    await call.message.edit_reply_markup(reply_markup=kb.procedures(selected))
    await call.answer()


async def _available_days(duration: int) -> list[date]:
    current = now()
    blocked = await db.blocked_days()
    days = candidate_days(current.date(), blocked)
    if not days:
        return []
    busy = await db.busy_intervals(day_bounds(days[0])[0], day_bounds(days[-1])[1])
    return [d for d in days if free_slots(d, duration, busy, current, blocked)]


async def show_days(call: CallbackQuery, state: FSMContext) -> None:
    chosen, total, minutes = _summary(await state.get_data())
    days = await _available_days(minutes)
    header = (f"Обрано: {', '.join(p.name for p in chosen)}\n"
              f"💰 {total} {config.CURRENCY} · ⏱ {fmt_duration(minutes)}\n\n")
    if not days:
        await state.set_state(Booking.procedures)
        await _edit(call, header + "😔 На найближчі дні вільного часу немає. "
                    f"Зателефонуйте нам: {escape(config.SALON_PHONE)}",
                    kb.procedures([p.id for p in chosen]))
        await call.answer()
        return
    await state.set_state(Booking.day)
    await _edit(call, header + "Оберіть дату 👇", kb.days(days))
    await call.answer()


@router.callback_query(Booking.day, F.data.startswith("day:"))
async def choose_day(call: CallbackQuery, state: FSMContext) -> None:
    day = date.fromisoformat(call.data.split(":", 1)[1])
    _, _, minutes = _summary(await state.get_data())
    blocked = await db.blocked_days()
    busy = await db.busy_intervals(*day_bounds(day))
    slots = free_slots(day, minutes, busy, now(), blocked)
    if not slots:
        await call.answer("На цю дату вже немає вільного часу", show_alert=True)
        await show_days(call, state)
        return
    await state.update_data(day=day.isoformat())
    await state.set_state(Booking.time)
    await _edit(call, f"📅 {fmt_day(day)}\nОберіть час початку 👇", kb.times(slots))
    await call.answer()


@router.callback_query(Booking.time, F.data.startswith("time:"))
async def choose_time(call: CallbackQuery, state: FSMContext) -> None:
    hhmm = call.data.split(":", 1)[1]
    data = await state.get_data()
    day = date.fromisoformat(data["day"])
    start_dt = datetime(day.year, day.month, day.day, int(hhmm[:2]), int(hhmm[2:]),
                        tzinfo=config.TZ)
    await state.update_data(start=start_dt.isoformat())
    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer()
    if data.get("name") and data.get("phone"):  # повернулися змінити час
        await ask_confirm(call.message, state)
        return
    await state.set_state(Booking.name)
    await call.message.answer(f"⏰ {fmt_day(day)}, {start_dt:%H:%M}\n\n"
                              "Як до вас звертатися? Напишіть ім'я.",
                              reply_markup=ReplyKeyboardRemove())


@router.message(Booking.name, F.text)
async def enter_name(message: Message, state: FSMContext) -> None:
    name = " ".join(message.text.split())
    if not 2 <= len(name) <= 60:
        await message.answer("Будь ласка, введіть ім'я (від 2 до 60 символів).")
        return
    await state.update_data(name=name)
    await state.set_state(Booking.phone)
    await message.answer("Надішліть номер телефону кнопкою нижче або введіть його вручну "
                         "(наприклад, +380671234567).", reply_markup=kb.phone_request())


PHONE_RE = re.compile(r"^\+?\d{10,13}$")


@router.message(Booking.phone, F.contact | F.text)
async def enter_phone(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    phone = re.sub(r"[\s\-()]", "", raw or "")
    if not PHONE_RE.match(phone):
        await message.answer("Не схоже на номер телефону 🤔 Спробуйте ще раз, "
                             "наприклад: +380671234567")
        return
    if not phone.startswith("+") and len(phone) == 12:
        phone = "+" + phone
    await state.update_data(phone=phone)
    await ask_confirm(message, state)


async def ask_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    chosen, total, minutes = _summary(data)
    start_dt = datetime.fromisoformat(data["start"])
    end_dt = start_dt + timedelta(minutes=minutes)
    await state.set_state(Booking.confirm)
    await message.answer("Дякуємо! Перевірте дані:", reply_markup=kb.main_menu())
    await message.answer(
        f"🗓 <b>{fmt_day(start_dt.date())}, {start_dt:%H:%M}–{end_dt:%H:%M}</b>\n"
        f"💆 {', '.join(p.name for p in chosen)}\n"
        f"💰 {total} {config.CURRENCY} · ⏱ {fmt_duration(minutes)}\n"
        f"👤 {escape(data['name'])}\n"
        f"📞 {escape(data['phone'])}\n\n"
        "Оплата на місці після процедури.",
        reply_markup=kb.confirm())


@router.callback_query(Booking.confirm, F.data == "flow:confirm")
async def confirm(call: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    chosen, total, minutes = _summary(data)
    start_dt = datetime.fromisoformat(data["start"])
    if start_dt < now() + timedelta(minutes=config.MIN_LEAD_MIN // 2):
        await call.answer("Цей час уже минув, оберіть інший", show_alert=True)
        await show_days(call, state)
        return
    try:
        b = await db.create_booking(
            user_id=call.from_user.id, username=call.from_user.username,
            client_name=data["name"], phone=data["phone"],
            procedures="; ".join(p.name for p in chosen),
            price=total, duration=minutes, start=start_dt)
    except db.SlotTaken:
        await call.answer("На жаль, цей час щойно зайняли. Оберіть інший.", show_alert=True)
        await show_days(call, state)
        return
    await state.clear()
    await _edit(call, f"✅ <b>Вас записано!</b>\n\n{texts.booking_card(b)}\n\n"
                      f"📍 {escape(config.SALON_ADDRESS)}\n\n{config.PREPARATION_TIPS}\n\n"
                      "Ми нагадаємо про візит. Скасувати запис можна в розділі "
                      f"«{kb.BTN_MY}».")
    await call.answer("Готово!")
    await notify_admins(bot, f"🆕 <b>Новий запис</b>\n\n{texts.booking_card(b, with_client=True)}")


@router.callback_query(F.data == "back:procs")
async def back_procs(call: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(Booking.procedures)
    await _edit(call, "Оберіть одну або кілька зон 👇", kb.procedures(data.get("selected", [])))
    await call.answer()


@router.callback_query(F.data == "back:days")
async def back_days(call: CallbackQuery, state: FSMContext) -> None:
    if not (await state.get_data()).get("selected"):
        await stale(call, state)
        return
    await show_days(call, state)


@router.callback_query(F.data == "flow:cancel")
async def flow_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _edit(call, "Запис скасовано. Повертайтеся, коли буде зручно 🙂")
    await call.answer()


@router.callback_query(F.data.regexp(r"^(proc|day|time|flow):"))
async def stale(call: CallbackQuery, state: FSMContext) -> None:
    """Натиснули кнопку зі старого повідомлення."""
    await call.answer(f"Ця кнопка застаріла. Натисніть «{kb.BTN_BOOK}», щоб почати заново.",
                      show_alert=True)


@router.message(StateFilter(Booking.procedures, Booking.day, Booking.time, Booking.confirm))
async def use_buttons(message: Message) -> None:
    await message.answer("Скористайтеся, будь ласка, кнопками вище 👆 "
                         f"або натисніть «{kb.BTN_BOOK}», щоб почати заново.")


@router.message(StateFilter(None))
async def fallback(message: Message) -> None:
    await message.answer("Оберіть дію в меню 👇", reply_markup=kb.main_menu())
