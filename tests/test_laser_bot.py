"""Тести бота запису на лазерну епіляцію (python -m unittest)."""
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from itertools import count

_tmp = tempfile.mkdtemp()
os.environ["DB_PATH"] = os.path.join(_tmp, "test.sqlite3")
os.environ["ADMIN_IDS"] = "999"
os.environ.setdefault("BOT_TOKEN", "")

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.methods import TelegramMethod  # noqa: E402
from aiogram.types import CallbackQuery, Chat, Contact, Message, Update, User  # noqa: E402

from laser_bot import config, db  # noqa: E402
from laser_bot.handlers import admin, client  # noqa: E402
from laser_bot.slots import candidate_days, free_slots  # noqa: E402

TZ = config.TZ
MONDAY = date(2026, 11, 2)


def at(d, hh, mm=0):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=TZ)


class SlotsTest(unittest.TestCase):
    def test_weekend_has_no_slots(self):
        saturday = MONDAY + timedelta(days=5)
        self.assertEqual(free_slots(saturday, 30, [], at(MONDAY, 0)), [])
        self.assertNotIn(saturday, candidate_days(MONDAY))

    def test_full_free_day(self):
        slots = free_slots(MONDAY, 30, [], at(MONDAY - timedelta(days=1), 12))
        self.assertEqual(slots[0], at(MONDAY, 8))
        self.assertEqual(slots[-1], at(MONDAY, 17, 30))   # 17:30 + 30 хв = 18:00
        self.assertEqual(len(slots), 20)

    def test_long_procedure_ends_before_closing(self):
        slots = free_slots(MONDAY, 100, [], at(MONDAY - timedelta(days=1), 12))
        self.assertEqual(slots[-1], at(MONDAY, 16))       # 16:00–17:40

    def test_busy_interval_and_lead_time(self):
        busy = [(at(MONDAY, 10), at(MONDAY, 11))]
        slots = free_slots(MONDAY, 60, busy, now=at(MONDAY, 8, 10))
        self.assertNotIn(at(MONDAY, 9), slots)            # менше ніж за годину
        self.assertNotIn(at(MONDAY, 9, 30), slots)        # перетин із 10:00
        self.assertNotIn(at(MONDAY, 10, 30), slots)
        self.assertIn(at(MONDAY, 11), slots)

    def test_blocked_day(self):
        self.assertEqual(free_slots(MONDAY, 30, [], at(MONDAY, 0), {MONDAY}), [])


class DbTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.path.exists(config.DB_PATH):
            os.remove(config.DB_PATH)
        await db.init()

    async def test_overlap_is_rejected(self):
        args = dict(user_id=1, username=None, client_name="Оля", phone="+380671234567",
                    procedures="Пахви", price=400, duration=60)
        start = at(MONDAY + timedelta(days=7), 10)
        b = await db.create_booking(start=start, **args)
        self.assertEqual(b.end, start + timedelta(hours=1))
        with self.assertRaises(db.SlotTaken):
            await db.create_booking(start=start + timedelta(minutes=30), **args)
        await db.create_booking(start=start + timedelta(hours=1), **args)  # впритул — можна
        await db.cancel_booking(b.id)
        await db.create_booking(start=start, **args)  # після скасування час вільний


class FakeSession(BaseSession):
    """Сесія, що не ходить у мережу, а записує всі виклики API."""

    def __init__(self):
        super().__init__()
        self.calls = []
        self.ids = count(1000)

    async def make_request(self, bot, method: TelegramMethod, timeout=None):
        self.calls.append(method)
        if method.__returning__ is bool:
            return True
        chat_id = getattr(method, "chat_id", None) or 1
        return Message(message_id=next(self.ids), date=datetime.now(),
                       chat=Chat(id=chat_id, type="private"),
                       text=getattr(method, "text", None))

    async def stream_content(self, *a, **kw):  # pragma: no cover
        yield b""

    async def close(self):
        pass


class FlowTest(unittest.IsolatedAsyncioTestCase):
    """Повний сценарій запису через диспетчер aiogram."""

    async def asyncSetUp(self):
        if os.path.exists(config.DB_PATH):
            os.remove(config.DB_PATH)
        await db.init()
        self.session = FakeSession()
        self.bot = Bot("42:TEST", session=self.session)
        self.dp = Dispatcher()
        self.dp.include_routers(admin.router, client.router)
        self.user = User(id=555, is_bot=False, first_name="Оля", username="olya")
        self.chat = Chat(id=555, type="private")
        self.uid = count(1)

    async def asyncTearDown(self):
        # роутери можна підключити лише до одного диспетчера
        admin.router._parent_router = None
        client.router._parent_router = None

    def _msg(self, **kw):
        return Message(message_id=next(self.uid), date=datetime.now(), chat=self.chat,
                       from_user=self.user, **kw)

    async def send(self, **kw):
        self.session.calls.clear()
        await self.dp.feed_update(self.bot, Update(update_id=next(self.uid), message=self._msg(**kw)))
        return self.session.calls[:]

    async def press(self, data):
        self.session.calls.clear()
        cq = CallbackQuery(id=str(next(self.uid)), from_user=self.user, chat_instance="x",
                           data=data, message=self._msg(text="old"))
        await self.dp.feed_update(self.bot, Update(update_id=next(self.uid), callback_query=cq))
        return self.session.calls[:]

    @staticmethod
    def buttons(calls):
        result = []
        for c in calls:
            markup = getattr(c, "reply_markup", None)
            for row in getattr(markup, "inline_keyboard", None) or []:
                result += [b.callback_data for b in row]
        return result

    async def test_booking_flow(self):
        calls = await self.send(text="/start")
        self.assertIn("Вітаємо", calls[0].text)

        calls = await self.send(text="💰 Ціни")
        self.assertIn("Пахви", calls[0].text)

        await self.send(text="📅 Записатися")
        await self.press("proc:arm")
        calls = await self.press("proc:bikini")
        self.assertIn("proc:done", self.buttons(calls))

        calls = await self.press("proc:done")
        days = [b for b in self.buttons(calls) if b.startswith("day:")]
        self.assertTrue(days)
        calls = await self.press(days[-1])
        times = [b for b in self.buttons(calls) if b.startswith("time:")]
        self.assertTrue(times)
        await self.press(times[0])

        await self.send(text="О")                       # закоротке ім'я
        await self.send(text="Ольга")
        calls = await self.send(text="12345")            # некоректний телефон
        self.assertIn("Не схоже", calls[0].text)
        calls = await self.send(contact=Contact(phone_number="380671234567", first_name="Оля"))
        self.assertIn("flow:confirm", self.buttons(calls))
        self.assertIn("35 хв", calls[-1].text)          # 15 + 20 хв
        self.assertIn("900 грн", calls[-1].text)        # 400 + 500

        calls = await self.press("flow:confirm")
        texts_sent = " ".join(c.text or "" for c in calls if hasattr(c, "text"))
        self.assertIn("Вас записано", texts_sent)
        admin_msgs = [c for c in calls if getattr(c, "chat_id", None) == 999]
        self.assertEqual(len(admin_msgs), 1)
        self.assertIn("+380671234567", admin_msgs[0].text)

        upcoming = await db.user_upcoming(555, datetime.now(TZ))
        self.assertEqual(len(upcoming), 1)
        b = upcoming[0]
        self.assertEqual((b.price, b.duration, b.client_name), (900, 35, "Ольга"))

        # слот зник із вільних
        calls_day = days[-1]
        await self.send(text="📅 Записатися")
        await self.press("proc:arm")
        await self.press("proc:done")
        calls = await self.press(calls_day)
        self.assertNotIn(times[0], self.buttons(calls))

        # скасування клієнтом
        calls = await self.send(text="📋 Мої записи")
        self.assertIn(f"mycancel:{b.id}", self.buttons(calls))
        await self.press(f"mycancel:{b.id}")
        await self.press(f"mycancel_yes:{b.id}")
        self.assertEqual((await db.get_booking(b.id)).status, "cancelled")


if __name__ == "__main__":
    unittest.main()
