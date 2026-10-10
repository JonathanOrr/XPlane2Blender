"""
Every screenshot in the docs: what is selected, what it shows and how the docs tests tell that it is out of date.
make_screenshots.py takes them in Blender windows; the docs tests draw the same panels and menus without a window and
fail when one no longer draws what its screenshot shows. Pictures of the 3D view's own drawing (click zones, motion
paths) are out of date when the code that draws them changes.
"""

import dataclasses
import hashlib
import importlib
import os
from typing import Dict, List, Optional, Tuple

import bpy

# The 3D view's overlays and the cockpit they are drawn on
VIEWPORT_SOURCES = (
    "viewport/draw.py",
    "viewport/overlay.py",
    "viewport/overlay_more.py",
    "viewport/motion.py",
    "viewport/lever.py",
    "viewport/light_shapes.py",
)


@dataclasses.dataclass(frozen=True)
class Shot:
    name: str
    tab: str  # A Properties editor tab as space.context names it, or VIEW_3D
    panels: Tuple[str, ...] = ()  # The add-on's top-level panels shown, in order
    select: Optional[str] = None  # The active object
    collection: Optional[str] = None  # The active collection (Collection tab)
    height: int = (
        1100  # Window height in pixels; a Properties picture is cut to what the panels fill
    )
    then: Optional[str] = (
        None  # A function of scenes.py run after selecting, for a panel in use
    )
    menu: Optional[str] = None  # A menu or pie menu shown open in the 3D view
    functions: Tuple[
        str, ...
    ] = ()  # Draw functions the add-on adds to Blender's own panels ("module.function")
    sources: Tuple[str, ...] = ()  # Files of the add-on whose drawing the picture shows
    open: Tuple[
        str, ...
    ] = ()  # Sub-panels closed by default that the picture shows open
    hide: Tuple[
        str, ...
    ] = ()  # Sub-panels left out of the picture, shown in another one (windows are 1120 px tall at most)

    @property
    def width(self) -> int:
        return 560 if self.tab != "VIEW_3D" else 1400


SHOTS: List[Shot] = [
    Shot(
        "object_not_exported",
        "OBJECT",
        ("XPLANE_PT_object",),
        select="coffee cup",
        height=800,
    ),
    Shot(
        "object_button", "OBJECT", ("XPLANE_PT_object",), select="landing light button"
    ),
    Shot(
        "object_touch_screen",
        "OBJECT",
        ("XPLANE_PT_object",),
        select="primary flight display",
        then="touch_screen",
    ),
    Shot(
        "object_knob",
        "OBJECT",
        ("XPLANE_PT_object",),
        select="heading knob",
        height=1100,
    ),
    Shot(
        "object_cards",
        "OBJECT",
        ("XPLANE_PT_object",),
        select="landing light button",
        then="cards",
        open=("XPLANE_PT_visibility", "XPLANE_PT_glow", "XPLANE_PT_more"),
        hide=("XPLANE_PT_click", "XPLANE_PT_motion"),
    ),
    Shot("object_spill_light", "OBJECT", ("XPLANE_PT_object",), select="flood light"),
    Shot("object_library_light", "OBJECT", ("XPLANE_PT_object",), select="dome light"),
    Shot(
        "object_attachment",
        "OBJECT",
        ("XPLANE_PT_object",),
        select="tablet mount",
        height=900,
    ),
    Shot(
        "material_screen",
        "MATERIAL",
        ("XPLANE_PT_surface",),
        select="primary flight display",
    ),
    Shot(
        "collection_file",
        "COLLECTION",
        ("XPLANE_PT_collection",),
        select="glareshield panel",
        collection="cockpit",
        height=700,
    ),
    Shot(
        "scene_export",
        "SCENE",
        ("XPLANE_PT_export",),
        select="glareshield panel",
        height=1100,
    ),
    Shot(
        "scene_file_rain",
        "SCENE",
        ("XPLANE_PT_export",),
        select="glareshield panel",
        open=("XPLANE_PT_file_rain",),
        hide=(
            "XPLANE_PT_file",
            "XPLANE_PT_file_decals",
            "XPLANE_PT_file_more",
            "XPLANE_PT_export_options",
        ),
    ),
    Shot(
        "scene_file_more",
        "SCENE",
        ("XPLANE_PT_export",),
        select="glareshield panel",
        open=(
            "XPLANE_PT_file_decals",
            "XPLANE_PT_file_more",
            "XPLANE_PT_export_options",
        ),
        hide=("XPLANE_PT_file", "XPLANE_PT_file_rain"),
    ),
    Shot(
        "scene_unfinished",
        "SCENE",
        ("XPLANE_PT_check",),
        select="glareshield panel",
        height=800,
        then="checked",
    ),
    Shot(
        "scene_tools",
        "SCENE",
        ("XPLANE_PT_tools",),
        select="glareshield panel",
        height=800,
    ),
    Shot(
        "scene_find_replace",
        "SCENE",
        ("XPLANE_PT_bulk_edit",),
        select="heading knob",
        height=1100,
        then="find_and_replace",
    ),
    Shot(
        "scene_tables",
        "SCENE",
        ("XPLANE_PT_table",),
        select="glareshield panel",
        height=900,
    ),
    Shot(
        "viewport_overlays",
        "VIEW_3D",
        select="throttle lever",
        height=900,
        then="overlays_on",
        functions=("io_xplane2blender.viewport.overlay.overlay_popover",),
        sources=VIEWPORT_SOURCES,
    ),
    Shot(
        "viewport_pie",
        "VIEW_3D",
        select="heading knob",
        height=900,
        then="overlays_on",
        menu="XPLANE_MT_pie",
        sources=VIEWPORT_SOURCES,
    ),
    Shot(
        "viewport_add_menu",
        "VIEW_3D",
        select="glareshield panel",
        height=900,
        menu="XPLANE_MT_add",
    ),
    Shot(
        "viewport_control_kind",
        "VIEW_3D",
        select="glareshield panel",
        height=900,
        menu="XPLANE_MT_control_kind",
    ),
]

BY_NAME: Dict[str, Shot] = {shot.name: shot for shot in SHOTS}


def view_context() -> Dict[str, object]:
    """The Layout workspace's screen and 3D View, which menus opened in the 3D View draw for"""
    screen = bpy.data.screens.get("Layout")
    space = None
    if screen is not None:
        area = max(
            (a for a in screen.areas if a.type == "VIEW_3D"),
            key=lambda a: a.width * a.height,
            default=None,
        )
        space = area.spaces.active if area else None
    return {"screen": screen, "space_data": space}


def overrides(shot: Shot) -> Dict[str, object]:
    """The context the shot's panels are drawn with"""
    obj = bpy.context.view_layer.objects.active
    found: Dict[str, object] = {"object": obj, "active_object": obj, **view_context()}
    if shot.tab == "MATERIAL":
        found["material"] = obj.active_material if obj else None
    if shot.collection:
        found["collection"] = bpy.data.collections[shot.collection]
    return found


def _folder() -> str:
    """Where the demo file is saved, as a user's file would be: the export button needs a folder to write the OBJs to"""
    import tempfile

    if bpy.app.background:
        # Tests run side by side, each saves its own
        return os.path.join(tempfile.gettempdir(), f"xp2b_docs_{os.getpid()}")
    return os.path.join(tempfile.gettempdir(), "xp2b_docs")


def prepare(shot: Shot) -> None:
    """Builds the demo scene and selects what the shot shows"""
    import scenes

    scenes.build()
    os.makedirs(_folder(), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(_folder(), "demo_cockpit.blend"), check_existing=False
    )
    if shot.select:
        scenes.select(shot.select)
    if shot.collection:
        layer = bpy.context.view_layer.layer_collection.children[shot.collection]
        bpy.context.view_layer.active_layer_collection = layer
    if shot.then:
        getattr(scenes, shot.then)()


def _source_hash(paths: Tuple[str, ...]) -> str:
    import io_xplane2blender

    root = os.path.dirname(io_xplane2blender.__file__)
    digest = hashlib.sha1()
    for path in paths:
        with open(os.path.join(root, path), "rb") as f:
            digest.update(f.read().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def record(shot: Shot) -> List[dict]:
    """What the shot's panels and menus draw, as the docs tests compare it"""
    import ui_recorder

    found = []
    context = overrides(shot)
    with ui_recorder.fixed_line_width():
        for idname in shot.panels:
            node = ui_recorder.record_panel(
                getattr(bpy.types, idname), context, True, shot.open, shot.hide
            )
            if node is not None:
                found.append(node)
        if shot.menu:
            found.append(
                ui_recorder.record_menu(getattr(bpy.types, shot.menu), context)
            )
        for path in shot.functions:
            module, _, name = path.rpartition(".")
            found.append(
                ui_recorder.record_function(
                    getattr(importlib.import_module(module), name), context
                )
            )
    found = ui_recorder.without_notes(found)
    if shot.sources:
        found.append(
            {
                "kind": "sources",
                "files": list(shot.sources),
                "sha1": _source_hash(shot.sources),
            }
        )
    # The demo file's folder is a different one on every computer
    import json

    text = json.dumps(found).replace(
        json.dumps(_folder() + os.sep)[1:-1], "<demo folder>/"
    )
    text = text.replace(json.dumps(_folder())[1:-1], "<demo folder>")
    # Nor is the add-on's version a reason to take a picture again
    import re

    return json.loads(re.sub(r'"Add-on [^"]+"', '"Add-on <version>"', text))
