"""Розрахунок вільних дат і годин (чиста логіка, без Telegram і БД)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from . import config

WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]


def is_working_day(day: date, blocked: set[date] = frozenset()) -> bool:
    return day.weekday() in config.WORK_DAYS and day not in blocked


def candidate_days(today: date, blocked: set[date] = frozenset()) -> list[date]:
    """Робочі дні в межах DAYS_AHEAD, починаючи з сьогодні."""
    days = (today + timedelta(days=i) for i in range(config.DAYS_AHEAD + 1))
    return [d for d in days if is_working_day(d, blocked)]


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, config.WORK_START, tzinfo=config.TZ)
    end = datetime.combine(day, config.WORK_END, tzinfo=config.TZ)
    return start, end


def free_slots(
    day: date,
    duration_min: int,
    busy: list[tuple[datetime, datetime]],
    now: datetime,
    blocked: set[date] = frozenset(),
) -> list[datetime]:
    """Години початку, на які можна записати процедуру тривалістю duration_min.

    busy — список зайнятих інтервалів (початок, кінець) інших записів.
    Після кожної процедури резервується BREAK_AFTER_MIN хвилин.
    """
    if duration_min <= 0 or not is_working_day(day, blocked):
        return []
    day_start, day_end = day_bounds(day)
    earliest = now + timedelta(minutes=config.MIN_LEAD_MIN)
    length = timedelta(minutes=duration_min)
    step = timedelta(minutes=config.SLOT_STEP_MIN)
    brk = timedelta(minutes=config.BREAK_AFTER_MIN)

    result = []
    start = day_start
    while start + length <= day_end:
        end = start + length
        if start >= earliest and not any(start < b_end + brk and b_start < end + brk
                                         for b_start, b_end in busy):
            result.append(start)
        start += step
    return result


def fmt_day(day: date) -> str:
    return f"{WEEKDAYS[day.weekday()]} {day:%d.%m}"


def fmt_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} год {m} хв"
    return f"{h} год" if h else f"{m} хв"
