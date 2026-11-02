"""Клавіатури бота."""
from __future__ import annotations

from datetime import date, datetime

from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import config
from .slots import fmt_day, fmt_duration

BTN_BOOK = "📅 Записатися"
BTN_PRICES = "💰 Ціни"
BTN_MY = "📋 Мої записи"
BTN_CONTACTS = "📍 Контакти"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_BOOK), KeyboardButton(text=BTN_PRICES)],
                  [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_CONTACTS)]],
        resize_keyboard=True,
    )


def phone_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Надіслати мій номер", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True,
    )


def _cancel_row() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text="✖️ Скасувати запис", callback_data="flow:cancel")]


def procedures(selected: list[str]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for p in config.PROCEDURES:
        mark = "✅ " if p.id in selected else ""
        kb.row(InlineKeyboardButton(
            text=f"{mark}{p.name} — {p.price} {config.CURRENCY}",
            callback_data=f"proc:{p.id}"))
    if selected:
        chosen = [config.PROCEDURES_BY_ID[i] for i in selected]
        total = sum(p.price for p in chosen)
        minutes = sum(p.duration for p in chosen)
        kb.row(InlineKeyboardButton(
            text=f"Далі ➡️  {total} {config.CURRENCY} · {fmt_duration(minutes)}",
            callback_data="proc:done"))
    kb.row(*_cancel_row())
    return kb.as_markup()


def days(available: list[date]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for d in available:
        kb.button(text=fmt_day(d), callback_data=f"day:{d.isoformat()}")
    kb.adjust(3)
    kb.row(InlineKeyboardButton(text="⬅️ Змінити процедури", callback_data="back:procs"))
    kb.row(*_cancel_row())
    return kb.as_markup()


def times(slots: list[datetime]) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for s in slots:
        kb.button(text=f"{s:%H:%M}", callback_data=f"time:{s:%H%M}")
    kb.adjust(4)
    kb.row(InlineKeyboardButton(text="⬅️ Інша дата", callback_data="back:days"))
    kb.row(*_cancel_row())
    return kb.as_markup()


def confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити", callback_data="flow:confirm")],
        [InlineKeyboardButton(text="⬅️ Змінити час", callback_data="back:days")],
        _cancel_row(),
    ])


def my_booking(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text="❌ Скасувати цей запис", callback_data=f"mycancel:{booking_id}")]])


def my_booking_confirm(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Так, скасувати", callback_data=f"mycancel_yes:{booking_id}"),
        InlineKeyboardButton(text="Ні, залишити", callback_data=f"mycancel_no:{booking_id}"),
    ]])


def admin_booking(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=f"❌ Скасувати #{booking_id}", callback_data=f"admcancel:{booking_id}")]])
