"""Рендер сценарію: кадри → накладки (титри, лічильник днів) → переходи → ffmpeg."""
import shutil
import subprocess
import sys

import yaml
from PIL import Image

from .canvas import LOGICAL_W, Ctx, find_font
from .easing import clamp01, lerp, window
from .scenes import SCENES

DEFAULT_VIDEO = {"width": 1280, "height": 720, "fps": 24, "supersample": 2,
                 "font": None, "audio": None, "crf": 18}


def load_scenario(path_or_dict):
    if isinstance(path_or_dict, dict):
        data = path_or_dict
    else:
        with open(path_or_dict, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    video = {**DEFAULT_VIDEO, **(data.get("video") or {})}
    scenes = data.get("scenes") or []
    if not scenes:
        raise ValueError("Сценарій не містить жодної сцени (scenes: [...])")
    start = 0.0
    for i, sc in enumerate(scenes):
        if sc.get("type") not in SCENES:
            raise ValueError(f"Сцена #{i}: невідомий тип {sc.get('type')!r}. "
                             f"Доступні: {', '.join(sorted(SCENES))}")
        sc["_start"] = start
        start += float(sc.get("duration", 3))
    return {"video": video, "scenes": scenes, "duration": start}


def scene_at(scn, t):
    for sc in scn["scenes"]:
        if t < sc["_start"] + float(sc.get("duration", 3)):
            return sc
    return scn["scenes"][-1]


# --- накладки ----------------------------------------------------------------
def draw_day_counter(ctx, sc, t, u):
    day = sc.get("day")
    if day is None:
        return
    if isinstance(day, (list, tuple)):
        day = int(round(lerp(day[0], day[1], u)))
    if sc.get("day_style", "small") == "big":
        ctx.text(40, 30, f"DAY {day}.", size=96, fill=(250, 250, 250), anchor="la")
    else:
        ctx.text(28, 24, f"DAY {day}", size=26, fill=(200, 200, 205), anchor="la")


def draw_captions(ctx, sc, t):
    for cap in sc.get("captions") or []:
        start = float(cap.get("start", 0))
        end = float(cap.get("end", float(sc.get("duration", 3))))
        a = window(t, start, end, float(cap.get("fade", 0.3)))
        if a <= 0:
            continue
        text = str(cap["text"])
        if cap.get("typewriter"):
            cps = float(cap.get("cps", 14))
            text = text[: max(0, int((t - start) * cps))]
        pos = cap.get("pos", "bottom")
        y = {"top": ctx.H * 0.14, "center": ctx.H * 0.5, "bottom": ctx.H * 0.88}.get(pos, pos)
        x = cap.get("x", ctx.W / 2)
        ctx.text(x, y, text, size=float(cap.get("size", 40)),
                 fill=tuple(cap.get("color", (245, 245, 245))), alpha=a)


def scene_fade(sc, t):
    dur = float(sc.get("duration", 3))
    fi, fo = float(sc.get("fade_in", 0)), float(sc.get("fade_out", 0))
    f = 1.0
    if fi > 0:
        f = min(f, clamp01(t / fi))
    if fo > 0:
        f = min(f, clamp01((dur - t) / fo))
    return f


# --- кадр -------------------------------------------------------------------
def render_frame(scn, t):
    v = scn["video"]
    ss = int(v["supersample"])
    k = v["width"] * ss / LOGICAL_W  # сцени малюються в логічних 1280 по ширині
    font = find_font(v.get("font"))
    sc = scene_at(scn, t)
    local = t - sc["_start"]
    dur = float(sc.get("duration", 3))
    u = clamp01(local / dur) if dur > 0 else 0.0

    img = Image.new("RGB", (v["width"] * ss, v["height"] * ss))
    ctx = Ctx(img, k, font)
    SCENES[sc["type"]](ctx, local, u, sc)
    draw_day_counter(ctx, sc, local, u)
    draw_captions(ctx, sc, local)

    if ss > 1:
        img = img.resize((v["width"], v["height"]), Image.LANCZOS)
    f = scene_fade(sc, local)
    if f < 1:
        img = Image.blend(Image.new("RGB", img.size), img, f)
    return img


def _ffmpeg_cmd(v, out, audio):
    enc = ["-c:v", "libx264", "-preset", "medium", "-crf", str(v["crf"])]
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    if "libx264" not in probe.stdout:
        enc = ["-c:v", "mpeg4", "-q:v", "3"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{v['width']}x{v['height']}", "-r", str(v["fps"]), "-i", "-"]
    if audio:
        cmd += ["-i", audio, "-c:a", "aac", "-shortest"]
    return cmd + enc + ["-pix_fmt", "yuv420p", "-movflags", "+faststart", out]


def render_video(scn, out, start=0.0, end=None, quiet=False):
    if not shutil.which("ffmpeg"):
        raise RuntimeError("Не знайдено ffmpeg. Встановіть його: https://ffmpeg.org/download.html")
    v = scn["video"]
    end = scn["duration"] if end is None else min(end, scn["duration"])
    fps = v["fps"]
    n = max(1, int(round((end - start) * fps)))
    proc = subprocess.Popen(_ffmpeg_cmd(v, out, v.get("audio")), stdin=subprocess.PIPE)
    try:
        for i in range(n):
            proc.stdin.write(render_frame(scn, start + i / fps).tobytes())
            if not quiet and (i % fps == 0 or i == n - 1):
                sys.stderr.write(f"\r  кадр {i + 1}/{n}")
                sys.stderr.flush()
    finally:
        proc.stdin.close()
        code = proc.wait()
    if not quiet:
        sys.stderr.write("\n")
    if code != 0:
        raise RuntimeError(f"ffmpeg завершився з кодом {code}")
    return n
