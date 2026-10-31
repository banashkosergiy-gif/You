"""Функції пом'якшення (easing) та інтерполяції."""
import math


def clamp01(t: float) -> float:
    return max(0.0, min(1.0, t))


def lerp(a, b, t: float):
    return a + (b - a) * t


def lerp_color(c1, c2, t: float):
    return tuple(int(round(lerp(a, b, t))) for a, b in zip(c1, c2))


def linear(t: float) -> float:
    return t


def ease_in_out(t: float) -> float:
    return 0.5 - 0.5 * math.cos(math.pi * clamp01(t))


def ease_out(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 2


def ease_in(t: float) -> float:
    return clamp01(t) ** 2


def window(t: float, start: float, end: float, fade: float = 0.3) -> float:
    """Непрозорість елемента, видимого в [start, end] з плавною появою/зникненням."""
    if t < start or t > end:
        return 0.0
    fade = max(1e-6, min(fade, (end - start) / 2))
    return clamp01(min((t - start) / fade, (end - t) / fade))
