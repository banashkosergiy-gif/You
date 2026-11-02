"""Налаштування бота: прайс, графік роботи, контакти.

Щоб змінити ціни чи графік, достатньо відредагувати цей файл
і перезапустити бота.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo


def _load_dotenv(path: Path) -> None:
    """Мінімальний завантажувач .env (без зовнішніх залежностей)."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(Path(__file__).with_name(".env"))


# ---------------------------------------------------------------- прайс ---

@dataclass(frozen=True)
class Procedure:
    id: str
    name: str
    price: int      # грн
    duration: int   # хвилини
    category: str


# Тестові ціни та тривалість. Замініть на свої.
PROCEDURES: list[Procedure] = [
    # Обличчя
    Procedure("lip", "Верхня губа", 250, 10, "Обличчя"),
    Procedure("chin", "Підборіддя", 250, 10, "Обличчя"),
    Procedure("face", "Обличчя повністю", 700, 30, "Обличчя"),
    # Тіло
    Procedure("arm", "Пахви", 400, 15, "Тіло"),
    Procedure("belly", "Біла лінія живота", 300, 10, "Тіло"),
    Procedure("back", "Спина", 1100, 45, "Тіло"),
    Procedure("arms_half", "Руки до ліктя", 600, 20, "Тіло"),
    Procedure("arms_full", "Руки повністю", 900, 40, "Тіло"),
    # Бікіні
    Procedure("bikini", "Бікіні класичне", 500, 20, "Бікіні"),
    Procedure("bikini_deep", "Бікіні глибоке", 750, 30, "Бікіні"),
    # Ноги
    Procedure("shins", "Гомілки", 800, 30, "Ноги"),
    Procedure("hips", "Стегна", 900, 30, "Ноги"),
    Procedure("legs_full", "Ноги повністю", 1400, 60, "Ноги"),
    # Комплекси (вигідніше, ніж окремо)
    Procedure("set_mini", "Комплекс «Міні»: пахви + бікіні класичне", 800, 35, "Комплекси"),
    Procedure("set_max",
              "Комплекс «Максі»: пахви + бікіні глибоке + ноги повністю",
              2300, 100, "Комплекси"),
]

PROCEDURES_BY_ID: dict[str, Procedure] = {p.id: p for p in PROCEDURES}
CATEGORIES: list[str] = list(dict.fromkeys(p.category for p in PROCEDURES))

CURRENCY = "грн"

# --------------------------------------------------------------- графік ---

TZ = ZoneInfo(os.getenv("TZ_NAME", "Europe/Kyiv"))
WORK_DAYS = {0, 1, 2, 3, 4}       # 0 = понеділок ... 6 = неділя
WORK_START = time(8, 0)
WORK_END = time(18, 0)            # процедура має закінчитися до цього часу
SLOT_STEP_MIN = 30                # крок, з яким пропонуються години
BREAK_AFTER_MIN = 0               # технічна перерва після кожної процедури
DAYS_AHEAD = 14                   # на скільки днів уперед можна записатися
MIN_LEAD_MIN = 60                 # мінімум хвилин до початку запису

# --------------------------------------------------------------- салон ----

SALON_NAME = os.getenv("SALON_NAME", "Laser Studio (тест)")
SALON_ADDRESS = os.getenv("SALON_ADDRESS", "м. Київ, вул. Прикладна, 1")
SALON_PHONE = os.getenv("SALON_PHONE", "+380 00 000 00 00")

PREPARATION_TIPS = (
    "ℹ️ <b>Як підготуватися:</b>\n"
    "• поголіть зону за 1–2 доби до процедури (не воском і не епілятором);\n"
    "• не засмагайте за 2 тижні до та після процедури;\n"
    "• у день процедури не наносьте на зону креми й дезодорант."
)

# ------------------------------------------------------------ технічне ----

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: set[int] = {
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
}
DB_PATH = os.getenv("DB_PATH", str(Path(__file__).with_name("bookings.sqlite3")))
