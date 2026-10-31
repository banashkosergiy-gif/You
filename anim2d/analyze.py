"""Аналіз готового відео: метадані, ключові кадри, зміни сцен, контактний аркуш.

Корисно, щоб «розкласти» референсне відео на сцени перед тим, як писати власний сценарій.
"""
import json
import os
import re
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw

from .canvas import _load_font, find_font


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format",
                          "-show_streams", path], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), {})
    num, _, den = v.get("avg_frame_rate", "0/1").partition("/")
    return {
        "duration": float(data["format"].get("duration", 0)),
        "width": v.get("width"),
        "height": v.get("height"),
        "fps": round(float(num) / float(den or 1), 3) if float(den or 1) else None,
        "has_audio": any(s["codec_type"] == "audio" for s in data["streams"]),
    }


def frame_at(path, t, width=480):
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
                          "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                         capture_output=True, check=True)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(out.stdout)
    try:
        return Image.open(f.name).convert("RGB")
    finally:
        os.unlink(f.name)


def scene_changes(path, threshold=0.15):
    """Часові мітки різкої зміни картинки (фільтр ffmpeg scene)."""
    res = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf",
                          f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
                         capture_output=True, text=True)
    return [float(m) for m in re.findall(r"pts_time:([0-9.]+)", res.stderr)]


def frame_stats(img):
    a = np.asarray(img, dtype=np.float32) / 255.0
    lum = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    small = img.resize((48, 27)).quantize(colors=4).convert("RGB")
    colors = sorted(small.getcolors(48 * 27), reverse=True)[:4]
    return {"brightness": round(float(lum.mean()), 3),
            "contrast": round(float(lum.std()), 3),
            "palette": ["#%02x%02x%02x" % c for _, c in colors]}


def contact_sheet(frames, labels, cols=4, pad=8, font_path=None):
    w, h = frames[0].size
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (w + pad) + pad, rows * (h + pad + 28) + pad), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    font = _load_font(find_font(font_path), 18)
    for i, (fr, lab) in enumerate(zip(frames, labels)):
        x = pad + (i % cols) * (w + pad)
        y = pad + (i // cols) * (h + pad + 28)
        sheet.paste(fr, (x, y))
        d.text((x + 4, y + h + 4), lab, fill=(220, 220, 220), font=font)
    return sheet


def analyze(path, n=12, threshold=0.15, use_scenes=True):
    meta = probe(path)
    dur = meta["duration"]
    cuts = scene_changes(path, threshold) if use_scenes else []
    times = sorted(set([round(t, 2) for t in cuts] +
                       [round(dur * (i + 0.5) / n, 2) for i in range(n)]))
    frames, report = [], []
    for t in times:
        img = frame_at(path, t)
        frames.append(img)
        report.append({"time": t, "is_cut": any(abs(t - c) < 0.01 for c in cuts),
                       **frame_stats(img)})
    return meta, cuts, frames, report
