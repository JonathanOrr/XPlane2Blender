"""
Takes the screenshots of the docs in Blender windows, one window per screenshot, and writes next to each picture what
its panels drew (docs/images/<name>.ui.json), which the docs tests compare against.

    python3 docs/tools/make_screenshots.py --blender /path/to/blender [shot names...]

Blender opens with factory settings at a fixed size and closes by itself. Use the Blender version the docs tests check
the screenshots with (the major and minor version in docs/images/blender_version.txt).
"""

import argparse
import json
import os
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(TOOLS))
IMAGES = os.path.join(REPO, "docs", "images")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--blender", required=True)
    parser.add_argument("names", nargs="*", help="Only these shots (default: all)")
    args = parser.parse_args()
    sys.path.insert(0, TOOLS)
    sys.modules.setdefault(
        "bpy", type(sys)("bpy")
    )  # shots.py imports bpy, it is not used out here
    from shots import SHOTS

    # Started with a file, Blender does not show its splash screen over the pictures
    import tempfile

    start = os.path.join(tempfile.gettempdir(), "xp2b_docs", "start.blend")
    os.makedirs(os.path.dirname(start), exist_ok=True)
    subprocess.run(
        [
            args.blender,
            "-b",
            "--factory-startup",
            "--python-expr",
            f"import bpy; bpy.ops.wm.save_as_mainfile(filepath={start!r})",
        ],
        capture_output=True,
        timeout=120,
    )
    names = args.names or [shot.name for shot in SHOTS]
    failed = []
    for shot in SHOTS:
        if shot.name not in names:
            continue
        command = [
            args.blender,
            "--factory-startup",
            "--window-geometry",
            "0",
            "0",
            str(shot.width),
            str(shot.height),
            start,
            "--python",
            os.path.join(TOOLS, "capture.py"),
            "--",
            shot.name,
        ]
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
        ok = (
            os.path.exists(os.path.join(IMAGES, shot.name + ".png"))
            and "CAPTURED" in result.stdout
        )
        print(("ok    " if ok else "FAILED"), shot.name)
        if not ok:
            failed.append(shot.name)
            print(result.stdout[-3000:], result.stderr[-3000:])
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
