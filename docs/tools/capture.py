"""
Runs inside a Blender window (see make_screenshots.py): builds the demo scene, shows one shot's panels alone in a
Properties editor that fills the window, saves the picture cut to the panels and what they drew, and quits.
"""

import json
import os
import sys

import bpy

TOOLS = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(TOOLS))
IMAGES = os.path.join(REPO, "docs", "images")
sys.path[:0] = [REPO, TOOLS]

import io_xplane2blender  # noqa: E402

io_xplane2blender.register()

import numpy as np  # noqa: E402
from shots import BY_NAME, prepare, record  # noqa: E402

SHOT = BY_NAME[sys.argv[sys.argv.index("--") + 1]]
bpy.context.preferences.view.show_tooltips = (
    False  # One would cover the menu under the mouse
)


def _depth(cls) -> int:
    depth = 0
    while getattr(cls, "bl_parent_id", ""):
        cls = getattr(bpy.types, cls.bl_parent_id, None)
        depth += 1
        if cls is None:
            break
    return depth


def _root(cls) -> str:
    while getattr(cls, "bl_parent_id", ""):
        parent = getattr(bpy.types, cls.bl_parent_id, None)
        if parent is None:
            break
        cls = parent
    return getattr(cls, "bl_idname", cls.__name__)


def _within(cls, idname: str) -> bool:
    """The panel is idname or one of its sub-panels"""
    while cls is not None:
        if getattr(cls, "bl_idname", cls.__name__) == idname:
            return True
        cls = getattr(bpy.types, getattr(cls, "bl_parent_id", "") or "-", None)
    return False


def hide_other_panels() -> None:
    """Only the shot's panels are left in its tab: Blender's own come first and would push them down"""
    tab = SHOT.tab.lower()
    others = []
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        if (
            not (isinstance(cls, type) and issubclass(cls, bpy.types.Panel))
            or cls is bpy.types.Panel
        ):
            continue
        if (
            getattr(cls, "bl_space_type", "") != "PROPERTIES"
            or getattr(cls, "bl_context", "") != tab
        ):
            continue
        if _root(cls) not in SHOT.panels or any(
            _within(cls, hidden) for hidden in SHOT.hide
        ):
            others.append(cls)
    for cls in sorted(others, key=_depth, reverse=True):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


def open_shot_panels() -> None:
    """A panel closed by default would show only its header: the shot's own are registered again open"""
    for idname in SHOT.panels + SHOT.open:
        cls = getattr(bpy.types, idname)
        if "DEFAULT_CLOSED" not in getattr(cls, "bl_options", set()):
            continue
        family = [
            c
            for c in (getattr(bpy.types, n) for n in dir(bpy.types))
            if isinstance(c, type)
            and issubclass(c, bpy.types.Panel)
            and _within(c, idname)
        ]
        for c in sorted(family, key=_depth, reverse=True):
            bpy.utils.unregister_class(c)
        cls.bl_options = set(cls.bl_options) - {"DEFAULT_CLOSED"}
        for c in sorted(family, key=_depth):
            bpy.utils.register_class(c)


def properties_area():
    return max(
        (a for a in bpy.context.window.screen.areas if a.type == "PROPERTIES"),
        key=lambda a: a.height,
    )


def view3d_area():
    return max(
        (a for a in bpy.context.window.screen.areas if a.type == "VIEW_3D"),
        key=lambda a: a.width * a.height,
    )


def setup_viewport():
    """The 3D view looking at the glareshield from the pilot's seat, a menu open in the middle of it"""
    import math

    from mathutils import Euler

    prepare(SHOT)
    area = view3d_area()
    space = area.spaces.active
    space.shading.type = "SOLID"
    space.overlay.show_overlays = True
    view = space.region_3d
    view.view_perspective = "PERSP"
    view.view_location = (0.0, 0.46, 0.92)
    view.view_distance = 0.62
    view.view_rotation = Euler((math.radians(60), 0, math.radians(-32))).to_quaternion()
    for obj in bpy.context.view_layer.objects:
        if obj.type == "LIGHT":
            obj.hide_set(True)  # Their cones cross the whole picture
    return 1.0


def open_menu():
    area = view3d_area()
    region = next(r for r in area.regions if r.type == "WINDOW")
    bpy.context.window.cursor_warp(
        region.x + region.width // 2, region.y + region.height // 2
    )
    with bpy.context.temp_override(window=bpy.context.window, area=area, region=region):
        if SHOT.menu.endswith("_pie"):
            bpy.ops.wm.call_menu_pie(name=SHOT.menu)
        else:
            bpy.ops.wm.call_menu(name=SHOT.menu)
    return 1.0


def take_viewport():
    area = view3d_area()
    path = os.path.join(IMAGES, SHOT.name + ".png")
    with bpy.context.temp_override(window=bpy.context.window, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    return finish()


def setup():
    prepare(SHOT)
    area = properties_area()
    area.spaces.active.context = SHOT.tab
    with bpy.context.temp_override(
        window=bpy.context.window, area=area, region=area.regions[-1]
    ):
        bpy.ops.screen.screen_full_area()
    return 1.5


def crop(path: str) -> None:
    """Cut the picture just under the last panel"""
    image = bpy.data.images.load(path)
    width, height = image.size
    pixels = np.empty(width * height * 4, dtype=np.float32)
    image.pixels.foreach_get(pixels)
    pixels = pixels.reshape(height, width, 4)  # The first row is the bottom one
    region = pixels[:, width // 8 : width - 24, :3]
    background = region[0, region.shape[1] // 2]
    drawn = np.abs(region - background).max(axis=2).max(axis=1) > 0.02
    rows = np.nonzero(drawn)[0]
    bottom = max(0, int(rows.min()) - 12) if len(rows) else 0
    cut = pixels[bottom:]
    out = bpy.data.images.new("cut", width, cut.shape[0], alpha=True)
    out.pixels.foreach_set(cut.ravel())
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()


def take():
    area = properties_area()
    path = os.path.join(IMAGES, SHOT.name + ".png")
    with bpy.context.temp_override(window=bpy.context.window, area=area):
        bpy.ops.screen.screenshot_area(filepath=path)
    crop(path)
    return finish()


def finish():
    with open(os.path.join(IMAGES, SHOT.name + ".ui.json"), "w") as f:
        json.dump(record(SHOT), f, indent=1, sort_keys=True)
        f.write("\n")
    with open(os.path.join(IMAGES, "blender_version.txt"), "w") as f:
        f.write("%d.%d\n" % bpy.app.version[:2])
    print("CAPTURED", SHOT.name)
    bpy.ops.wm.quit_blender()
    return None


# Before Blender first draws the panels: it remembers whether each one is open once it has drawn it
if SHOT.tab != "VIEW_3D":
    hide_other_panels()
    open_shot_panels()

if SHOT.tab == "VIEW_3D":
    STEPS = [setup_viewport] + ([open_menu] if SHOT.menu else []) + [take_viewport]
else:
    STEPS = [setup, take]


def tick():
    try:
        return STEPS.pop(0)()
    except Exception:
        import traceback

        traceback.print_exc()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=1.5)
