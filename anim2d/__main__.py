"""CLI:
  python -m anim2d render  examples/morning_run.yaml -o out/morning_run.mp4
  python -m anim2d preview examples/morning_run.yaml -t 5.5 -o out/frame.png
  python -m anim2d sheet   examples/morning_run.yaml -o out/storyboard.png
  python -m anim2d analyze some_video.mp4 -o out/analysis
  python -m anim2d scenes
"""
import argparse
import json
import os
import sys

from .scenes import SCENES


def _ensure_dir(path):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="anim2d", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render", help="зрендерити сценарій у MP4")
    r.add_argument("scenario")
    r.add_argument("-o", "--out", default="out/video.mp4")
    r.add_argument("--start", type=float, default=0.0)
    r.add_argument("--end", type=float)
    r.add_argument("--fps", type=int)
    r.add_argument("--draft", action="store_true", help="швидкий чорновик: пів роздільності, 12 fps, без згладжування")

    p = sub.add_parser("preview", help="один кадр у PNG")
    p.add_argument("scenario")
    p.add_argument("-t", "--time", type=float, default=0.0)
    p.add_argument("-o", "--out", default="out/frame.png")

    s = sub.add_parser("sheet", help="розкадровка: по кадру з середини кожної сцени")
    s.add_argument("scenario")
    s.add_argument("-o", "--out", default="out/storyboard.png")
    s.add_argument("--cols", type=int, default=3)

    a = sub.add_parser("analyze", help="аналіз готового відео")
    a.add_argument("video")
    a.add_argument("-o", "--out", default="out/analysis")
    a.add_argument("-n", type=int, default=12, help="скільки рівномірних кадрів")
    a.add_argument("--threshold", type=float, default=0.15,
                   help="поріг детекції зміни сцени (0.15 — для темної мінімалістичної анімації)")
    a.add_argument("--no-scenes", action="store_true")

    sub.add_parser("scenes", help="список доступних типів сцен")

    args = ap.parse_args(argv)

    if args.cmd == "scenes":
        for name, fn in sorted(SCENES.items()):
            print(f"{name:12s} {(fn.__doc__ or '').strip()}")
        return 0

    if args.cmd == "analyze":
        from .analyze import analyze, contact_sheet
        os.makedirs(args.out, exist_ok=True)
        meta, cuts, frames, report = analyze(args.video, args.n, args.threshold, not args.no_scenes)
        labels = [f"{r['time']:.1f}s" + (" ✂" if r["is_cut"] else "") for r in report]
        contact_sheet(frames, labels).save(os.path.join(args.out, "contact_sheet.png"))
        result = {"meta": meta, "scene_cuts": cuts, "frames": report}
        with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(json.dumps(meta, ensure_ascii=False))
        print(f"Змін сцен: {len(cuts)}; результати в {args.out}/")
        return 0

    from .render import load_scenario, render_frame, render_video
    scn = load_scenario(args.scenario)

    if args.cmd == "render":
        if args.fps:
            scn["video"]["fps"] = args.fps
        if args.draft:
            v = scn["video"]
            v.update(width=v["width"] // 2 // 2 * 2, height=v["height"] // 2 // 2 * 2,
                     supersample=1, fps=12)
        _ensure_dir(args.out)
        n = render_video(scn, args.out, args.start, args.end)
        print(f"Готово: {args.out} ({n} кадрів, {scn['duration']:.1f} с сценарію)")
    elif args.cmd == "preview":
        _ensure_dir(args.out)
        render_frame(scn, args.time).save(args.out)
        print(f"Кадр {args.time:.2f} с → {args.out}")
    elif args.cmd == "sheet":
        from .analyze import contact_sheet
        frames, labels = [], []
        for i, sc in enumerate(scn["scenes"]):
            t = sc["_start"] + float(sc.get("duration", 3)) * 0.6
            frames.append(render_frame(scn, t).resize((480, 270)))
            labels.append(f"#{i + 1} {sc['type']} @ {t:.1f}s")
        _ensure_dir(args.out)
        contact_sheet(frames, labels, cols=args.cols).save(args.out)
        print(f"Розкадровка → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
