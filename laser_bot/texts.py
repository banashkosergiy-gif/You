"""Тексти повідомлень."""
from __future__ import annotations

from html import escape

from . import config
from .db import Booking
from .slots import fmt_day, fmt_duration


def price_list() -> str:
    lines = [f"💰 <b>Прайс — {escape(config.SALON_NAME)}</b>"]
    for cat in config.CATEGORIES:
        lines.append(f"\n<b>{cat}</b>")
        for p in config.PROCEDURES:
            if p.category == cat:
                lines.append(f"• {p.name} — <b>{p.price} {config.CURRENCY}</b>"
                             f" <i>({fmt_duration(p.duration)})</i>")
    lines.append("\nЗа один візит можна обрати кілька зон, "
                 "ціна й тривалість підсумуються автоматично.")
    lines.append("\n" + config.PREPARATION_TIPS)
    return "\n".join(lines)


def contacts() -> str:
    days = ", ".join(["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"][d]
                     for d in sorted(config.WORK_DAYS))
    return (f"📍 <b>{escape(config.SALON_NAME)}</b>\n"
            f"Адреса: {escape(config.SALON_ADDRESS)}\n"
            f"Телефон: {escape(config.SALON_PHONE)}\n"
            f"Графік: {days}, {config.WORK_START:%H:%M}–{config.WORK_END:%H:%M}")


def booking_card(b: Booking, *, with_client: bool = False) -> str:
    text = (f"🗓 <b>{fmt_day(b.start.date())}, {b.start:%H:%M}–{b.end:%H:%M}</b>\n"
            f"💆 {escape(b.procedures)}\n"
            f"💰 {b.price} {config.CURRENCY} · ⏱ {fmt_duration(b.duration)}")
    if with_client:
        user = f" (@{escape(b.username)})" if b.username else ""
        text += (f"\n👤 {escape(b.client_name)}{user}\n"
                 f"📞 <code>{escape(b.phone)}</code>")
    return f"<b>Запис #{b.id}</b>\n{text}"
