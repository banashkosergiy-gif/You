import os
import shutil
import subprocess
import tempfile
import unittest

from anim2d.easing import ease_in_out, window
from anim2d.render import load_scenario, render_frame, render_video, scene_at
from anim2d.scenes import SCENES

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "morning_run.yaml")


def tiny(scene):
    return load_scenario({"video": {"width": 320, "height": 180, "fps": 4, "supersample": 1},
                          "scenes": [scene]})


class TestEasing(unittest.TestCase):
    def test_bounds(self):
        self.assertAlmostEqual(ease_in_out(0), 0)
        self.assertAlmostEqual(ease_in_out(1), 1)
        self.assertEqual(window(5, 1, 3), 0)
        self.assertEqual(window(2, 1, 3, fade=0.5), 1)


class TestScenario(unittest.TestCase):
    def test_example_loads(self):
        scn = load_scenario(EXAMPLE)
        self.assertGreater(scn["duration"], 10)
        self.assertEqual(scene_at(scn, 0)["type"], "title")

    def test_unknown_scene(self):
        with self.assertRaises(ValueError):
            load_scenario({"scenes": [{"type": "nope"}]})

    def test_every_scene_renders(self):
        for name in SCENES:
            img = render_frame(tiny({"type": name, "duration": 2, "day": [1, 5],
                                     "captions": [{"text": "Привіт", "start": 0, "end": 2}]}), 1.0)
            self.assertEqual(img.size, (320, 180), name)
            self.assertGreater(len(set(img.getdata())), 3, f"{name}: порожній кадр")

    def test_fade_in_starts_black(self):
        img = render_frame(tiny({"type": "title", "text": "X", "duration": 2, "fade_in": 1}), 0)
        self.assertEqual(img.getextrema(), ((0, 0), (0, 0), (0, 0)))


@unittest.skipUnless(shutil.which("ffmpeg"), "потрібен ffmpeg")
class TestVideo(unittest.TestCase):
    def test_render_and_analyze(self):
        from anim2d.analyze import analyze
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "v.mp4")
            scn = load_scenario({"video": {"width": 320, "height": 180, "fps": 8, "supersample": 1},
                                 "scenes": [{"type": "title", "text": "A", "duration": 1, "bg": [240, 240, 240]},
                                            {"type": "city_run", "duration": 1}]})
            self.assertEqual(render_video(scn, out, quiet=True), 16)
            meta, cuts, frames, report = analyze(out, n=4)
            self.assertAlmostEqual(meta["duration"], 2.0, delta=0.2)
            self.assertTrue(any(0.8 < c < 1.2 for c in cuts), cuts)


if __name__ == "__main__":
    unittest.main()
