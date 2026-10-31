"""Полотно з логічними координатами та суперсемплінгом (згладжування країв).

Усі функції малювання працюють у «логічних» координатах кадру (напр. 1280x720),
а Ctx сам множить їх на коефіцієнт суперсемплінгу k.
"""
import math
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

LOGICAL_W = 1280  # ширина «логічного» кадру, в якій описані всі сцени

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def find_font(path=None):
    """Шрифт з підтримкою кирилиці: явний шлях → системні кандидати → None."""
    if path and os.path.exists(path):
        return path
    for cand in FONT_CANDIDATES:
        if os.path.exists(cand):
            return cand
    return None


@lru_cache(maxsize=64)
def _load_font(path, px):
    if path:
        return ImageFont.truetype(path, px)
    return ImageFont.load_default(size=px)


def ellipse_points(cx, cy, rx, ry, angle=0.0, n=72, egg=0.0):
    """Точки (повернутого) еліпса. egg>0 робить низ ширшим — форма яйця."""
    ca, sa = math.cos(angle), math.sin(angle)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        x = rx * math.cos(a)
        y = ry * math.sin(a)
        x *= 1 + egg * math.sin(a)  # sin>0 → нижня половина
        pts.append((cx + x * ca - y * sa, cy + x * sa + y * ca))
    return pts


class Ctx:
    def __init__(self, img: Image.Image, k: float, font_path=None):
        self.img = img
        self.d = ImageDraw.Draw(img)
        self.k = k
        self.font_path = font_path
        self.W = img.width / k
        self.H = img.height / k

    # --- примітиви -------------------------------------------------------
    def _p(self, pts):
        k = self.k
        return [(x * k, y * k) for x, y in pts]

    def _w(self, width):
        return max(1, int(round(width * self.k))) if width else 0

    def fill(self, color):
        self.d.rectangle([0, 0, self.img.width, self.img.height], fill=color)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0, radius=0):
        box = [x0 * self.k, y0 * self.k, x1 * self.k, y1 * self.k]
        if radius:
            self.d.rounded_rectangle(box, radius=radius * self.k, fill=fill,
                                     outline=outline, width=self._w(width))
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=self._w(width))

    def ellipse(self, cx, cy, rx, ry, fill=None, outline=None, width=0):
        k = self.k
        self.d.ellipse([(cx - rx) * k, (cy - ry) * k, (cx + rx) * k, (cy + ry) * k],
                       fill=fill, outline=outline, width=self._w(width))

    def circle(self, cx, cy, r, fill=None, outline=None, width=0):
        self.ellipse(cx, cy, r, r, fill, outline, width)

    def line(self, pts, fill, width=4, round_caps=True):
        self.d.line(self._p(pts), fill=fill, width=self._w(width), joint="curve")
        if round_caps:
            r = width / 2
            for x, y in (pts[0], pts[-1]):
                self.circle(x, y, r, fill=fill)

    def polygon(self, pts, fill=None, outline=None, width=0):
        self.d.polygon(self._p(pts), fill=fill)
        if outline and width:
            self.line(list(pts) + [pts[0]], fill=outline, width=width, round_caps=False)

    # --- текст -----------------------------------------------------------
    def font(self, size):
        return _load_font(self.font_path, int(size * self.k))

    def text(self, x, y, s, size=32, fill=(255, 255, 255), anchor="mm", alpha=1.0):
        if alpha <= 0 or not s:
            return
        f = self.font(size)
        if alpha >= 1:
            self.d.text((x * self.k, y * self.k), s, font=f, fill=fill, anchor=anchor)
            return
        mask = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(mask).text((x * self.k, y * self.k), s, font=f,
                                  fill=int(255 * alpha), anchor=anchor)
        self.img.paste(fill, (0, 0), mask)

    def text_width(self, s, size):
        f = self.font(size)
        return f.getlength(s) / self.k


# --- семисегментний індикатор (для будильника) ----------------------------
_SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}


def seven_segment(ctx: Ctx, x, y, text, h=80, color=(230, 40, 40)):
    """Малює рядок типу '5:00' у стилі цифрового годинника. Повертає ширину."""
    w = h * 0.5
    th = h * 0.12
    gap = h * 0.18
    cx = x
    for ch in text:
        if ch == ":":
            ctx.circle(cx + th, y + h * 0.3, th * 0.6, fill=color)
            ctx.circle(cx + th, y + h * 0.7, th * 0.6, fill=color)
            cx += th * 2 + gap
            continue
        segs = _SEGMENTS.get(ch, "")
        boxes = {
            "a": (cx + th, y, cx + w - th, y + th),
            "b": (cx + w - th, y + th, cx + w, y + h / 2),
            "c": (cx + w - th, y + h / 2, cx + w, y + h - th),
            "d": (cx + th, y + h - th, cx + w - th, y + h),
            "e": (cx, y + h / 2, cx + th, y + h - th),
            "f": (cx, y + th, cx + th, y + h / 2),
            "g": (cx + th, y + h / 2 - th / 2, cx + w - th, y + h / 2 + th / 2),
        }
        for s in segs:
            ctx.rect(*boxes[s], fill=color, radius=th * 0.3)
        cx += w + gap
    return cx - x - gap


def seven_segment_width(text, h=80):
    w, th, gap = h * 0.5, h * 0.12, h * 0.18
    total = sum((th * 2 + gap) if ch == ":" else (w + gap) for ch in text)
    return total - gap
