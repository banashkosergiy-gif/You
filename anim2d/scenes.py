"""Бібліотека сцен. Кожна сцена: fn(ctx, t, u, sc), де
t — секунди від початку сцени, u ∈ [0,1] — прогрес сцени, sc — словник параметрів.

Будь-який числовий параметр можна задати як [від, до] — він анімується протягом сцени.
Щоб додати свою сцену, напишіть функцію і зареєструйте її декоратором @scene("назва").
"""
import math
import random

from .canvas import Ctx, seven_segment, seven_segment_width
from .character import draw_character
from .easing import ease_in_out, lerp, lerp_color

SCENES = {}


def scene(name):
    def deco(fn):
        SCENES[name] = fn
        return fn
    return deco


def P(sc, key, default, u):
    """Параметр сцени; [a, b] → плавна інтерполяція за прогресом u."""
    v = sc.get(key, default)
    if (isinstance(v, (list, tuple)) and len(v) == 2
            and all(isinstance(x, (int, float)) for x in v)):
        return lerp(v[0], v[1], ease_in_out(u))
    return v


def auto_blink(t, period=3.1):
    return (t % period) > period - 0.12


NIGHT_SKY = (22, 26, 48)
DAWN_SKY = (236, 156, 112)
DAY_SKY = (150, 196, 230)


def sky_color(light):
    """light: 0 — ніч, 0.5 — світанок, 1 — день."""
    if light < 0.5:
        return lerp_color(NIGHT_SKY, DAWN_SKY, light * 2)
    return lerp_color(DAWN_SKY, DAY_SKY, (light - 0.5) * 2)


# ---------------------------------------------------------------------------
@scene("title")
def title(ctx: Ctx, t, u, sc):
    ctx.fill(tuple(sc.get("bg", (10, 10, 12))))
    size = P(sc, "size", 120, u)
    ctx.text(ctx.W / 2, ctx.H / 2 - (30 if sc.get("subtitle") else 0), sc.get("text", ""),
             size=size, fill=tuple(sc.get("color", (245, 245, 245))))
    if sc.get("subtitle"):
        ctx.text(ctx.W / 2, ctx.H / 2 + size * 0.55, sc["subtitle"], size=size * 0.3,
                 fill=(170, 170, 175))


# ---------------------------------------------------------------------------
@scene("bedroom")
def bedroom(ctx: Ctx, t, u, sc):
    light = P(sc, "light", 0.0, u)
    room = lerp_color((14, 14, 18), (60, 52, 58), light)
    ctx.fill(room)

    # вікно з небом, місяцем або сонцем
    wx0, wy0, wx1, wy1 = 400, 70, 640, 270
    ctx.rect(wx0, wy0, wx1, wy1, fill=sky_color(light), outline=(70, 70, 80), width=8, radius=6)
    if light < 0.45:
        ctx.circle(590, 125, 26, fill=(235, 232, 210))
        ctx.circle(602, 117, 24, fill=sky_color(light))
    else:
        ctx.circle(470, 270 - 120 * (light - 0.45), 34, fill=(255, 214, 120))
        ctx.rect(wx0, wy1 - 4, wx1, wy1 + 40, fill=room)  # «горизонт» = підвіконня
    ctx.line([((wx0 + wx1) / 2, wy0), ((wx0 + wx1) / 2, wy1)], fill=(70, 70, 80), width=6)
    ctx.line([(wx0, (wy0 + wy1) / 2), (wx1, (wy0 + wy1) / 2)], fill=(70, 70, 80), width=6)

    line = (90, 90, 100)
    # ліжко
    ctx.rect(745, 330, 785, 650, fill=(52, 52, 62), outline=line, width=4, radius=20)
    ctx.rect(70, 520, 790, 600, fill=(48, 48, 58), outline=line, width=4, radius=14)
    ctx.rect(70, 600, 790, 640, fill=(36, 36, 44), outline=line, width=4, radius=8)
    ctx.ellipse(650, 505, 95, 32, fill=(78, 78, 92), outline=line, width=4)

    action = sc.get("action", "stare")
    expression = sc.get("expression", "sleeping" if action == "sleep" else "neutral")
    blink = action != "sleep" and auto_blink(t)
    draw_character(ctx, 615, 440, size=1.25, pose="head", expression=expression,
                   tilt=P(sc, "tilt", -0.22, u), look=P(sc, "look", 0.5, u), blink=blink)

    # ковдра поверх тіла
    blanket = [(60, 612), (60, 480), (190, 438), (370, 448), (520, 468), (590, 500),
               (625, 545), (640, 612)]
    ctx.polygon(blanket, fill=(46, 58, 92), outline=(22, 22, 28), width=4)
    ctx.line([(150, 470), (210, 560)], fill=(36, 46, 76), width=4)
    ctx.line([(380, 470), (420, 570)], fill=(36, 46, 76), width=4)

    if action == "sleep":
        for i in range(3):
            ph = (t * 0.6 + i / 3) % 1
            ctx.text(690 + 50 * ph + i * 6, 360 - 110 * ph, "z", size=26 + 20 * ph,
                     fill=(200, 200, 215), alpha=1 - ph)

    # тумбочка + будильник
    ctx.rect(820, 520, 1110, 700, fill=(38, 34, 34), outline=line, width=4, radius=10)
    ctx.circle(965, 610, 9, fill=(80, 80, 90))
    ringing = sc.get("ringing", False)
    shake = math.sin(t * 70) * 4 if ringing else 0.0
    ctx.rect(845 + shake, 395, 1085 + shake, 515, fill=(18, 18, 22), outline=line, width=6, radius=26)
    clock = str(sc.get("clock", "5:00"))
    h = 78
    cw = seven_segment_width(clock, h)
    seven_segment(ctx, 965 + shake - cw / 2, 416, clock, h=h,
                  color=tuple(sc.get("clock_color", (232, 42, 42))))
    if ringing and int(t * 8) % 2 == 0:
        for side in (-1, 1):
            bx = 965 + side * 150
            for j in range(3):
                ctx.line([(bx, 420 + j * 30), (bx + side * 26, 410 + j * 30)],
                         fill=(232, 42, 42), width=5)


# ---------------------------------------------------------------------------
@scene("mirror")
def mirror(ctx: Ctx, t, u, sc):
    ctx.fill((10, 10, 13))
    ctx.rect(0, 600, ctx.W, ctx.H, fill=(18, 18, 22))
    ctx.line([(0, 600), (ctx.W, 600)], fill=(40, 40, 48), width=3)
    draw_character(ctx, 380, 600, size=1.3, expression=sc.get("expression", "sad"),
                   look=0.7, blink=auto_blink(t))

    # дзеркало з «внутрішнім критиком»
    mx, my, rx, ry = 860, 360, 140, 220
    ctx.ellipse(mx, my, rx + 14, ry + 14, fill=(70, 60, 50))
    ctx.ellipse(mx, my, rx, ry, fill=(26, 10, 14))
    red = tuple(sc.get("critic_color", (210, 40, 52)))
    wob = lambda i, k=1.0: math.sin(t * 5 + i * 0.9) * 5 * k
    head = [(mx + 40 * math.cos(a) + wob(n), my - 110 + 62 * math.sin(a) + wob(n + 3))
            for n, a in enumerate([2 * math.pi * i / 28 for i in range(28)])]
    ctx.line(head + [head[0]], fill=red, width=5, round_caps=False)
    for side in (-1, 1):  # очі-щілини
        ctx.line([(mx + side * 26, my - 120), (mx + side * 8, my - 108)], fill=red, width=6)
    body = [(mx + wob(i, 1.6), my - 46 + i * 22) for i in range(10)]
    ctx.line(body, fill=red, width=6)
    for side in (-1, 1):
        arm = [(mx, my - 20), (mx + side * 60 + wob(1), my + 30), (mx + side * 70, my + 100 + wob(2))]
        ctx.line(arm, fill=red, width=5)


# ---------------------------------------------------------------------------
def _city_layer(seed, n, hmin, hmax, wmin, wmax):
    rnd = random.Random(seed)
    blds, x = [], 0
    for _ in range(n):
        w = rnd.randint(wmin, wmax)
        h = rnd.randint(hmin, hmax)
        wins = [(cx, cy, rnd.random() < 0.35)
                for cx in range(14, w - 14, 26) for cy in range(20, h - 20, 34)]
        blds.append((x, w, h, wins))
        x += w + rnd.randint(4, 30)
    return blds, x


_LAYERS = {}


@scene("city_run")
def city_run(ctx: Ctx, t, u, sc):
    light = P(sc, "light", 0.0, u)
    ground = 600
    ctx.fill(sky_color(light))
    if light < 0.4:
        ctx.circle(1050, 120, 30, fill=(235, 232, 210))
    else:
        ctx.circle(1050, ground - 40 - 420 * (light - 0.4), 46, fill=(255, 210, 120))

    speed = P(sc, "speed", 260, u)
    seed = sc.get("seed", 7)
    if seed not in _LAYERS:
        _LAYERS[seed] = (_city_layer(seed, 40, 150, 330, 70, 150),
                         _city_layer(seed + 1, 40, 90, 240, 60, 130))
    layers = _LAYERS[seed]
    tints = [lerp_color((30, 32, 50), (120, 110, 130), light),
             lerp_color((16, 16, 24), (70, 64, 80), light)]
    for (blds, period), factor, color in zip(layers, (0.25, 0.6), tints):
        off = (t * speed * factor) % period
        for rep in (0, 1):
            for bx, w, h, wins in blds:
                x0 = bx - off + rep * period
                if x0 > ctx.W or x0 + w < 0:
                    continue
                ctx.rect(x0, ground - h, x0 + w, ground, fill=color)
                if light < 0.7:
                    for cx, cy, lit in wins:
                        if lit:
                            ctx.rect(x0 + cx - 6, ground - h + cy, x0 + cx + 6,
                                     ground - h + cy + 14, fill=(250, 210, 120))

    ctx.rect(0, ground, ctx.W, ctx.H, fill=(22, 22, 26))
    dash = (t * speed) % 120
    for i in range(-1, int(ctx.W / 120) + 2):
        x = i * 120 - dash
        ctx.rect(x, 650, x + 60, 658, fill=(90, 90, 96))

    draw_character(ctx, P(sc, "x", 560, u), ground, size=1.2, pose="running",
                   expression=sc.get("expression", "determined"),
                   phase=t * P(sc, "cadence", 1.6, u))
