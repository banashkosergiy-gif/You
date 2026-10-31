"""Оригінальний персонаж «Піп»: голова-яйце з паростком, худі, ноги-палички.

Пози:      standing | running | head (лише голова, напр. на подушці)
Емоції:    neutral | determined | tired | happy | sad | sleeping
"""
import math

from .canvas import Ctx, ellipse_points

DEFAULT_PALETTE = {
    "skin": (236, 226, 206),
    "line": (22, 22, 28),
    "hoodie": (72, 108, 168),
    "leaf": (118, 178, 96),
    "eye": (22, 22, 28),
}

HEAD_RX, HEAD_RY = 48, 56


def _rot(cx, cy, angle, s):
    ca, sa = math.cos(angle), math.sin(angle)

    def T(lx, ly):
        lx, ly = lx * s, ly * s
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)

    return T


def draw_head(ctx: Ctx, cx, cy, size=1.0, expression="neutral", tilt=0.0,
              look=0.0, blink=False, palette=None):
    """Голова з обличчям. look ∈ [-1, 1] — куди дивиться (вліво/вправо)."""
    pal = {**DEFAULT_PALETTE, **(palette or {})}
    T = _rot(cx, cy, tilt, size)
    lw = 4 * size

    # паросток на маківці (малюємо першим — голова перекриє основу стебла)
    stem = [T(0, -HEAD_RY + 4), T(2, -HEAD_RY - 10), T(0, -HEAD_RY - 18)]
    ctx.line(stem, fill=pal["line"], width=lw * 0.8)
    for side in (-1, 1):
        lc = T(side * 11, -HEAD_RY - 20)
        leaf = ellipse_points(*lc, 12 * size, 5.5 * size, angle=tilt - side * 0.5, n=32)
        ctx.polygon(leaf, fill=pal["leaf"], outline=pal["line"], width=lw * 0.6)

    # голова-яйце
    head = ellipse_points(cx, cy, HEAD_RX * size, HEAD_RY * size, angle=tilt, egg=0.08)
    ctx.polygon(head, fill=pal["skin"], outline=pal["line"], width=lw)

    fx = 10 * look
    eyes = [(-17 + fx, -4), (17 + fx, -4)]
    ink = pal["eye"]

    # очі
    for ex, ey in eyes:
        if blink or expression == "sleeping":
            ctx.line([T(ex - 7, ey + 1), T(ex, ey + 4), T(ex + 7, ey + 1)], fill=ink, width=lw)
        elif expression == "happy":
            ctx.line([T(ex - 7, ey + 3), T(ex, ey - 4), T(ex + 7, ey + 3)], fill=ink, width=lw)
        elif expression == "tired":
            ctx.circle(*T(ex, ey + 1), 5.5 * size, fill=ink)
            lid = [T(ex - 9, ey - 9), T(ex + 9, ey - 9), T(ex + 9, ey + 1), T(ex - 9, ey + 1)]
            ctx.polygon(lid, fill=pal["skin"])
            ctx.line([T(ex - 8, ey + 1), T(ex + 8, ey + 1)], fill=ink, width=lw * 0.8)
        else:
            ctx.circle(*T(ex, ey), 6.5 * size, fill=ink)
            ctx.circle(*T(ex + 2, ey - 2), 1.8 * size, fill=(255, 255, 255))

    # брови
    brows = {
        "determined": [((-30, -24), (-8, -15)), ((30, -24), (8, -15))],
        "sad": [((-28, -15), (-8, -23)), ((28, -15), (8, -23))],
        "tired": [((-27, -17), (-9, -17)), ((27, -17), (9, -17))],
    }.get(expression)
    if brows:
        for (x0, y0), (x1, y1) in brows:
            ctx.line([T(x0 + fx, y0), T(x1 + fx, y1)], fill=ink, width=lw * 1.2)

    # рот: парабола, curve>0 — посмішка
    curve = {"happy": 8, "neutral": 0, "determined": -4, "sad": -7,
             "sleeping": 2, "tired": 0}.get(expression, 0)
    pts = []
    for i in range(13):
        u = -1 + 2 * i / 12
        y = 22 + curve * (1 - u * u)
        if expression == "tired":
            y = 22 + 2 * math.sin(u * 3 * math.pi)
        pts.append(T(fx + 12 * u, y))
    ctx.line(pts, fill=ink, width=lw)
    return T


def _limb(ctx, start, a1, a2, l1, l2, color, width):
    """Двосегментна кінцівка; кути від вертикалі вниз (рад)."""
    x0, y0 = start
    x1, y1 = x0 + l1 * math.sin(a1), y0 + l1 * math.cos(a1)
    x2, y2 = x1 + l2 * math.sin(a2), y1 + l2 * math.cos(a2)
    ctx.line([(x0, y0), (x1, y1), (x2, y2)], fill=color, width=width)


def draw_character(ctx: Ctx, x, y, size=1.0, pose="standing", expression="neutral",
                   phase=0.0, blink=False, tilt=0.0, look=None, palette=None):
    """(x, y) — точка на землі між ступнями; для pose='head' — центр голови."""
    pal = {**DEFAULT_PALETTE, **(palette or {})}
    if pose == "head":
        return draw_head(ctx, x, y, size, expression, tilt, look or 0.0, blink, pal)

    s = size
    lw = 6 * s
    leg, body_h, body_w = 56 * s, 70 * s, 54 * s
    running = pose == "running"
    swing = math.sin(phase * 2 * math.pi) if running else 0.0
    bob = abs(math.sin(phase * 2 * math.pi)) * 7 * s if running else 0.0
    lean = 10 * s if running else 0.0

    hip = (x, y - leg - bob)
    shoulder = (x + lean, hip[1] - body_h + 14 * s)

    def legs(sign):
        a = 0.75 * swing * sign
        knee = 0.9 * max(0.0, -swing * sign) + 0.2 if running else 0.0
        _limb(ctx, hip, a, a - knee, leg * 0.52, leg * 0.52, pal["line"], lw)

    def arms(sign):
        a = -0.9 * swing * sign if running else 0.12 * sign
        bend = 1.2 if running else 0.1
        _limb(ctx, shoulder, a, a + bend * (1 if running else sign * 0.3),
              24 * s, 22 * s, pal["line"], lw)

    # задні кінцівки → тіло → передні → голова
    legs(-1)
    arms(-1)
    body = [(hip[0] - body_w / 2 + lean * 0.3, hip[1]),
            (hip[0] + body_w / 2 + lean * 0.3, hip[1]),
            (shoulder[0] + body_w / 2 - 4 * s, shoulder[1] - 14 * s),
            (shoulder[0] - body_w / 2 + 4 * s, shoulder[1] - 14 * s)]
    ctx.polygon(body, fill=pal["hoodie"], outline=pal["line"], width=lw * 0.7)
    # кишеня-«кенгуру»
    ctx.line([(hip[0] - 14 * s + lean * 0.3, hip[1] - 22 * s),
              (hip[0] + 14 * s + lean * 0.3, hip[1] - 22 * s)], fill=pal["line"], width=lw * 0.5)
    legs(1)
    arms(1)

    head_c = (shoulder[0] + lean * 0.4, shoulder[1] - 14 * s - HEAD_RY * s + 6 * s)
    if look is None:
        look = 0.6 if running else 0.0
    return draw_head(ctx, *head_c, size=s, expression=expression,
                     tilt=tilt + (0.08 if running else 0.0), look=look, blink=blink, palette=pal)
