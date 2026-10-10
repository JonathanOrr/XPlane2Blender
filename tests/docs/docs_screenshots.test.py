"""
The screenshots in docs/ still show what the panels draw. Each screenshot was saved with what its panels drew
(docs/images/<name>.ui.json); this draws them again without a window and fails when they draw something else, until the
screenshots are taken again with docs/tools/make_screenshots.py.
"""

import json
import os
import sys

import bpy

from io_xplane2blender.tests import *

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGES = os.path.join(REPO, "docs", "images")
sys.path.insert(0, os.path.join(REPO, "docs", "tools"))

from shots import SHOTS, prepare, record  # noqa: E402


def _first_difference(old, new, path="") -> str:
    if type(old) is not type(new):
        return f"{path}: {json.dumps(old)[:120]} -> {json.dumps(new)[:120]}"
    if isinstance(old, dict):
        for key in sorted(set(old) | set(new)):
            if old.get(key) != new.get(key):
                return _first_difference(old.get(key), new.get(key), f"{path}.{key}")
    if isinstance(old, list):
        for i, (a, b) in enumerate(zip(old, new)):
            if a != b:
                label = a.get("text") or a.get("label") or a.get("kind") if isinstance(a, dict) else ""
                return _first_difference(a, b, f"{path}[{i}]({label})")
        if len(old) != len(new):
            return f"{path}: {len(old)} items -> {len(new)}"
    return f"{path}: {json.dumps(old)[:120]} -> {json.dumps(new)[:120]}"


class TestDocsScreenshots(XPlaneTestCase):
    def test_every_shot_has_its_picture(self) -> None:
        for shot in SHOTS:
            with self.subTest(shot=shot.name):
                self.assertTrue(os.path.exists(os.path.join(IMAGES, shot.name + ".png")), "take it with make_screenshots.py")
                self.assertTrue(os.path.exists(os.path.join(IMAGES, shot.name + ".ui.json")))

    def test_panels_still_draw_what_the_screenshots_show(self) -> None:
        with open(os.path.join(IMAGES, "blender_version.txt")) as f:
            version = f.read().strip()
        if version != "%d.%d" % bpy.app.version[:2]:
            self.skipTest(f"the screenshots were taken with Blender {version}")
        for shot in SHOTS:
            with self.subTest(shot=shot.name):
                with open(os.path.join(IMAGES, shot.name + ".ui.json")) as f:
                    saved = json.load(f)
                prepare(shot)
                now = json.loads(json.dumps(record(shot), sort_keys=True))
                self.assertTrue(
                    now == saved,
                    f"docs/images/{shot.name}.png is out of date, the panel now draws something else at"
                    f" {_first_difference(saved, now)}. Update the docs that describe it and take it again:"
                    f" python3 docs/tools/make_screenshots.py --blender <Blender {version}> {shot.name}",
                )


runTestCases([TestDocsScreenshots])
