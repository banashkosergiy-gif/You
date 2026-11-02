"""Зберігання записів у SQLite."""
from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import aiosqlite

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    username     TEXT,
    client_name  TEXT NOT NULL,
    phone        TEXT NOT NULL,
    procedures   TEXT NOT NULL,      -- назви процедур через "; "
    price        INTEGER NOT NULL,
    duration     INTEGER NOT NULL,   -- хвилини
    start_ts     INTEGER NOT NULL,   -- unix time (UTC)
    end_ts       INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active',   -- active | cancelled
    created_ts   INTEGER NOT NULL,
    reminded_24h INTEGER NOT NULL DEFAULT 0,
    reminded_2h  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_ts);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE TABLE IF NOT EXISTS blocked_days (
    day TEXT PRIMARY KEY             -- YYYY-MM-DD
);
"""


@dataclass
class Booking:
    id: int
    user_id: int
    username: str | None
    client_name: str
    phone: str
    procedures: str
    price: int
    duration: int
    start: datetime
    end: datetime
    status: str

    @classmethod
    def from_row(cls, row: aiosqlite.Row) -> "Booking":
        return cls(
            id=row["id"], user_id=row["user_id"], username=row["username"],
            client_name=row["client_name"], phone=row["phone"],
            procedures=row["procedures"], price=row["price"],
            duration=row["duration"],
            start=datetime.fromtimestamp(row["start_ts"], config.TZ),
            end=datetime.fromtimestamp(row["end_ts"], config.TZ),
            status=row["status"],
        )


class SlotTaken(Exception):
    """Обраний час уже зайнятий."""


@asynccontextmanager
async def _connect():
    async with aiosqlite.connect(config.DB_PATH, isolation_level=None) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def init() -> None:
    async with _connect() as conn:
        await conn.executescript(SCHEMA)


def _ts(dt: datetime) -> int:
    return int(dt.timestamp())


async def busy_intervals(day_start: datetime, day_end: datetime) -> list[tuple[datetime, datetime]]:
    margin = timedelta(minutes=config.BREAK_AFTER_MIN)
    async with _connect() as conn:
        cur = await conn.execute(
            "SELECT start_ts, end_ts FROM bookings "
            "WHERE status = 'active' AND start_ts < ? AND end_ts > ?",
            (_ts(day_end + margin), _ts(day_start - margin)),
        )
        rows = await cur.fetchall()
    return [(datetime.fromtimestamp(s, config.TZ), datetime.fromtimestamp(e, config.TZ))
            for s, e in rows]


async def create_booking(*, user_id: int, username: str | None, client_name: str,
                         phone: str, procedures: str, price: int, duration: int,
                         start: datetime) -> Booking:
    """Створює запис. Перевірка зайнятості й вставка — в одній транзакції."""
    end = start + timedelta(minutes=duration)
    brk = config.BREAK_AFTER_MIN * 60
    async with _connect() as conn:
        await conn.execute("BEGIN IMMEDIATE")
        try:
            cur = await conn.execute(
                "SELECT 1 FROM bookings WHERE status = 'active' "
                "AND start_ts < ? AND end_ts + ? > ? LIMIT 1",
                (_ts(end) + brk, brk, _ts(start)),
            )
            if await cur.fetchone():
                raise SlotTaken
            cur = await conn.execute(
                "INSERT INTO bookings (user_id, username, client_name, phone, procedures, "
                "price, duration, start_ts, end_ts, created_ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, client_name, phone, procedures, price, duration,
                 _ts(start), _ts(end), _ts(datetime.now(config.TZ))),
            )
            booking_id = cur.lastrowid
            await conn.execute("COMMIT")
        except BaseException:
            await conn.execute("ROLLBACK")
            raise
    return await get_booking(booking_id)


async def get_booking(booking_id: int) -> Booking | None:
    async with _connect() as conn:
        cur = await conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        row = await cur.fetchone()
    return Booking.from_row(row) if row else None


async def cancel_booking(booking_id: int) -> bool:
    async with _connect() as conn:
        cur = await conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'active'",
            (booking_id,),
        )
        return cur.rowcount > 0


async def user_upcoming(user_id: int, now: datetime) -> list[Booking]:
    async with _connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM bookings WHERE user_id = ? AND status = 'active' "
            "AND start_ts >= ? ORDER BY start_ts",
            (user_id, _ts(now)),
        )
        return [Booking.from_row(r) for r in await cur.fetchall()]


async def bookings_between(start: datetime, end: datetime) -> list[Booking]:
    async with _connect() as conn:
        cur = await conn.execute(
            "SELECT * FROM bookings WHERE status = 'active' "
            "AND start_ts >= ? AND start_ts < ? ORDER BY start_ts",
            (_ts(start), _ts(end)),
        )
        return [Booking.from_row(r) for r in await cur.fetchall()]


async def due_reminders(now: datetime, hours: int) -> list[Booking]:
    """Записи, яким пора надіслати нагадування за `hours` годин.

    Нагадування не надсилається, якщо запис створили вже менш ніж
    за `hours` годин до початку (клієнт і так щойно все бачив).
    """
    column = "reminded_24h" if hours == 24 else "reminded_2h"
    window = hours * 3600
    async with _connect() as conn:
        cur = await conn.execute(
            f"SELECT * FROM bookings WHERE status = 'active' AND {column} = 0 "
            "AND start_ts > ? AND start_ts <= ? AND start_ts - created_ts > ?",
            (_ts(now), _ts(now) + window, window),
        )
        return [Booking.from_row(r) for r in await cur.fetchall()]


async def mark_reminded(booking_id: int, hours: int) -> None:
    column = "reminded_24h" if hours == 24 else "reminded_2h"
    async with _connect() as conn:
        await conn.execute(f"UPDATE bookings SET {column} = 1 WHERE id = ?", (booking_id,))


async def blocked_days() -> set[date]:
    async with _connect() as conn:
        cur = await conn.execute("SELECT day FROM blocked_days")
        return {date.fromisoformat(r[0]) for r in await cur.fetchall()}


async def block_day(day: date) -> None:
    async with _connect() as conn:
        await conn.execute("INSERT OR IGNORE INTO blocked_days(day) VALUES (?)",
                           (day.isoformat(),))


async def unblock_day(day: date) -> bool:
    async with _connect() as conn:
        cur = await conn.execute("DELETE FROM blocked_days WHERE day = ?", (day.isoformat(),))
        return cur.rowcount > 0
