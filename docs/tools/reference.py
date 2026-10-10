"""
Writes docs/reference.md: every setting, button and menu of the add-on's panels under the name the panel shows, with
its tooltip and, where it depends on it, the kind of thing that shows it. The panels are drawn without a window in
each of their variants (every kind of control, light, attachment point, screen, table...), so the page lists what a
user can meet and cannot fall behind the add-on: the docs tests fail when it differs from what this writes.

    blender -b --factory-startup --python docs/tools/reference.py
"""

import os
import sys
from typing import Callable, Dict, List, Optional, Tuple

import bpy

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [TOOLS]
import shots  # noqa: E402

REPO = os.path.dirname(os.path.dirname(TOOLS))
PAGE = os.path.join(REPO, "docs", "reference.md")

HEADER = """# Settings Reference

Every setting, button and menu of the add-on's panels, under the name the panel shows, with its tooltip. Where a
setting only shows for some kinds of object, **Shown for** says which. The [guides](README.md) explain how they are
used.

<!-- Written by docs/tools/reference.py from the add-on itself. Do not edit by hand: run
     blender -b --factory-startup --python docs/tools/reference.py -->
"""


# ---- Variants: (label, what to set up) for each panel -----------------------------------------------------------------


def _enum_items(data, prop: str) -> List[str]:
    return [item.identifier for item in data.bl_rna.properties[prop].enum_items]


def _enum_name(data, prop: str, identifier: str) -> str:
    return next(
        item.name
        for item in data.bl_rna.properties[prop].enum_items
        if item.identifier == identifier
    )


def _set(path: str, value) -> Callable[[], None]:
    """A setup that sets one value, path from an object: 'heading knob:xplane.manip.type'"""

    def setup() -> None:
        name, _, attribute = path.partition(":")
        owner = _resolve(name)
        *parents, last = attribute.split(".")
        for part in parents:
            owner = getattr(owner, part)
        setattr(owner, last, value)

    return setup


def _resolve(name: str):
    kind, _, rest = name.partition("/")
    if kind == "material":
        return bpy.data.materials[rest]
    if kind == "collection":
        return bpy.data.collections[rest]
    if kind == "light":
        return bpy.data.lights[rest]
    if kind == "scene":
        return bpy.context.scene
    if kind == "wm":
        return bpy.context.window_manager
    if kind == "bone":
        return bpy.data.armatures["seat"].bones[rest]
    return bpy.data.objects[name]


def _steps(*setups: Callable[[], None]) -> Callable[[], None]:
    def setup() -> None:
        for step in setups:
            step()

    return setup


def _kind_label(kind: str) -> Optional[str]:
    """Some kinds of control share their name in the menu, under Runs commands and Sets a dataref"""
    if kind in ("command_knob", "command_switch_up_down", "command_switch_left_right"):
        return "{} (command)"
    if kind in ("axis_knob", "axis_switch_up_down", "axis_switch_left_right"):
        return "{} (dataref)"
    return None


# A section of the page: (tab, panel, active object, context overrides, variants as (label or None, setup))
Section = Tuple[
    str, str, str, Dict[str, str], List[Tuple[Optional[str], Callable[[], None]]]
]


def _sections() -> List[Section]:
    import scenes

    scenes.build()
    manip = bpy.data.objects["landing light button"].xplane.manip
    empty = bpy.data.objects["tablet mount"].xplane.special_empty_props
    light = bpy.data.lights["flood light"].xplane
    material = bpy.data.materials["pfd screen"].xplane
    layer = bpy.data.collections["cockpit"].xplane.layer
    table = bpy.context.window_manager.xplane_table
    none = [(None, lambda: None)]
    return [
        ("Object tab", "XPLANE_PT_object", "landing light button", {}, none),
        (
            "Object tab",
            "XPLANE_PT_click",
            "landing light button",
            {},
            [
                (
                    _kind_label(kind),
                    _set("landing light button:xplane.manip.type", kind),
                )
                for kind in _enum_items(manip, "type")
            ],
        ),
        ("Object tab", "XPLANE_PT_motion", "heading knob", {}, none),
        (
            "Object tab",
            "XPLANE_PT_visibility",
            "landing light button",
            {},
            [(None, scenes.cards)],
        ),
        (
            "Object tab",
            "XPLANE_PT_glow",
            "landing light button",
            {},
            [(None, scenes.cards)],
        ),
        (
            "Object tab",
            "XPLANE_PT_attachment",
            "tablet mount",
            {},
            [
                (
                    None,
                    _set("tablet mount:xplane.special_empty_props.special_type", kind),
                )
                for kind in _enum_items(empty, "special_type")
            ],
        ),
        (
            "Object tab",
            "XPLANE_PT_light",
            "flood light",
            {},
            [
                (None, _set("light/flood light:xplane.type", kind))
                for kind in _enum_items(light, "type")
            ],
        ),
        ("Object tab", "XPLANE_PT_light_more", "flood light", {}, none),
        (
            "Object tab",
            "XPLANE_PT_more",
            "landing light button",
            {},
            [
                ("any object", lambda: None),
                (
                    "Draw Order on",
                    _set("landing light button:xplane.override_weight", True),
                ),
                (
                    "its own file",
                    _set("landing light button:xplane.isExportableRoot", True),
                ),
            ],
        ),
        (
            "Material tab",
            "XPLANE_PT_surface",
            "primary flight display",
            {"material": "material/pfd screen"},
            [
                (
                    f"screen: {_enum_name(material, 'cockpit_feature', feature)}",
                    _set("material/pfd screen:xplane.cockpit_feature", feature),
                )
                for feature in _enum_items(material, "cockpit_feature")
            ]
            + [
                (
                    f"transparency: {_enum_name(material, 'blend_v1000', blend)}",
                    _set("material/pfd screen:xplane.blend_v1000", blend),
                )
                for blend in _enum_items(material, "blend_v1000")
            ],
        ),
        (
            "Material tab",
            "XPLANE_PT_surface_more",
            "primary flight display",
            {"material": "material/pfd screen"},
            [
                ("not a hard surface", lambda: None),
                (
                    "hard surface",
                    _set("material/pfd screen:xplane.surfaceType", "concrete"),
                ),
            ],
        ),
        ("Bone tab", "XPLANE_PT_bone", "seat rig", {"bone": "bone/seat slide"}, none),
        (
            "Bone tab",
            "XPLANE_PT_bone_moves",
            "seat rig",
            {"bone": "bone/seat slide"},
            none,
        ),
        (
            "Bone tab",
            "XPLANE_PT_bone_visibility",
            "seat rig",
            {"bone": "bone/seat slide"},
            none,
        ),
        (
            "Bone tab",
            "XPLANE_PT_bone_more",
            "seat rig",
            {"bone": "bone/seat slide"},
            none,
        ),
        (
            "Collection tab",
            "XPLANE_PT_collection",
            "glareshield panel",
            {"collection": "collection/cockpit"},
            [
                (None, _set("collection/cockpit:xplane.layer.export_type", kind))
                for kind in _enum_items(layer, "export_type")
            ],
        ),
        ("Scene tab", "XPLANE_PT_export", "glareshield panel", {}, none),
        (
            "Scene tab",
            "XPLANE_PT_file",
            "glareshield panel",
            {},
            [
                (
                    f"{_enum_name(layer, 'export_type', kind)} file",
                    _set("collection/cockpit:xplane.layer.export_type", kind),
                )
                for kind in _enum_items(layer, "export_type")
            ]
            + [
                (
                    f"panel texture: {_enum_name(layer, 'cockpit_panel_mode', mode)}",
                    _set("collection/cockpit:xplane.layer.cockpit_panel_mode", mode),
                )
                for mode in _enum_items(layer, "cockpit_panel_mode")
            ]
            + [
                (
                    f"normal and shine: {_enum_name(layer, 'normal_maps', way)}",
                    _set("collection/cockpit:xplane.layer.normal_maps", way),
                )
                for way in _enum_items(layer, "normal_maps")
            ]
            + [
                (
                    "two levels of detail",
                    _set("collection/cockpit:xplane.layer.lods", "2"),
                )
            ],
        ),
        (
            "Scene tab",
            "XPLANE_PT_file_rain",
            "glareshield panel",
            {},
            [
                ("nothing on", lambda: None),
                (
                    "a defrost source and a wiper on",
                    _steps(
                        _set(
                            "collection/cockpit:xplane.layer.rain.thermal_source_1_enabled",
                            True,
                        ),
                        _set(
                            "collection/cockpit:xplane.layer.rain.wiper_1_enabled", True
                        ),
                    ),
                ),
            ],
        ),
        (
            "Scene tab",
            "XPLANE_PT_file_decals",
            "glareshield panel",
            {},
            [
                ("no detail texture", lambda: None),
                (
                    "a detail texture set",
                    _set(
                        "collection/cockpit:xplane.layer.file_decal1",
                        "textures/detail.png",
                    ),
                ),
            ],
        ),
        ("Scene tab", "XPLANE_PT_file_more", "glareshield panel", {}, none),
        (
            "Scene tab",
            "XPLANE_PT_export_options",
            "glareshield panel",
            {},
            [
                ("", lambda: None),
                ("Developer Tools on", _set("scene:xplane.plugin_development", True)),
            ],
        ),
        (
            "Scene tab",
            "XPLANE_PT_check",
            "glareshield panel",
            {},
            [("before Check", lambda: None), ("after Check", scenes.checked)],
        ),
        ("Scene tab", "XPLANE_PT_tools", "glareshield panel", {}, none),
        (
            "Scene tab",
            "XPLANE_PT_bulk_edit",
            "heading knob",
            {},
            [(None, scenes.find_and_replace)],
        ),
        (
            "Scene tab",
            "XPLANE_PT_table",
            "glareshield panel",
            {},
            [
                (None, _set("wm:xplane_table.table", kind))
                for kind in _enum_items(table, "table")
            ],
        ),
    ]


# ---- Turning recordings into rows ------------------------------------------------------------------------------------


class _Walk:
    """Collects the settings, buttons and menus of a recording in the order they are drawn. A label names the setting
    drawn right after it, also inside the row or column that follows it, and buttons that each set one choice of the
    same setting (Smooth / Hard Edge / Cut Shadow) are one setting with those choices"""

    def __init__(self) -> None:
        self.found: List[Tuple[str, str, str]] = []
        self.choices: Dict[Tuple[str, str], List[str]] = {}
        self.label = ""
        self.choice: Optional[Tuple[str, str]] = None

    def walk(self, items: List[dict], header_of: Optional[str] = None) -> None:
        for item in items:
            kind = item.get("kind")
            if kind == "label":
                text = item["text"]
                # A short label names what follows it; a sentence is help text
                self.label = text if len(text) <= 40 and not text.endswith(".") else ""
                self.choice = None
                continue
            if kind == "prop_enum":
                if not (self.choice and self.choice[0] == item["prop"]):
                    self.choice = (item["prop"], self.label or item.get("_name", ""))
                    if self.choice not in self.choices:
                        self.choices[self.choice] = []
                        self.found.append(("choice", self.choice[1], self.choice[0]))
                self.choices[self.choice].append(item["text"])
                self.label = ""
                continue
            if isinstance(item.get("items"), list):
                self.walk(item["items"])
                continue
            self.choice = None
            if kind == "prop":
                name = (
                    item["text"]
                    or (f"{header_of} (on / off)" if header_of else self.label)
                    or item.get("_name", "")
                )
                tip = item.get("_tip", "")
                if item.get("_choices"):
                    tip = (
                        (tip + " " if tip else "")
                        + "Choices: "
                        + ", ".join(item["_choices"])
                        + "."
                    )
                self.found.append(("setting", name, tip))
            elif kind == "operator":
                # A button that only has an icon goes by the name its tooltip gives it
                kind = "button" if item["text"] else "icon button"
                self.found.append(
                    (kind, item["text"] or item.get("_name", ""), item.get("_tip", ""))
                )
            elif kind == "menu":
                # A menu button showing what is chosen: the menu's own name, and the choice it shows
                self.found.append(
                    (
                        "menu",
                        item.get("_name") or item["text"],
                        item.get("_tip", "") + "\0" + item["text"],
                    )
                )
            self.label = ""

    def rows(self) -> List[Tuple[str, str, str]]:
        rows = []
        for kind, name, tip in self.found:
            if kind == "choice":
                rows.append(
                    (
                        "setting",
                        name,
                        "Choices: " + ", ".join(self.choices[(tip, name)]) + ".",
                    )
                )
            else:
                rows.append((kind, name, tip))
        return rows


def _rows(
    items: List[dict], header_of: Optional[str] = None
) -> List[Tuple[str, str, str]]:
    """(kind, name, tooltip) of the settings, buttons and menus in a recording"""
    walk = _Walk()
    walk.walk(items, header_of)
    return walk.rows()


def _shown(names: List[str], labels: List[str]) -> str:
    missing = [label for label in labels if label not in names]
    if not missing:
        return ""
    if len(missing) < len(names):
        return "all but " + ", ".join(missing)
    return ", ".join(names)


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _record(
    panel: str, active: str, overrides: Dict[str, str], setup: Callable[[], None]
) -> Tuple[str, List[tuple]]:
    import scenes
    import ui_recorder

    scenes.build()
    obj = scenes.select(active)
    setup()
    context = {"object": obj, "active_object": obj, **shots.view_context()}
    context.update({key: _resolve(value) for key, value in overrides.items()})
    with ui_recorder.fixed_line_width():
        node = ui_recorder.record_panel(
            getattr(bpy.types, panel), context, children=False, opened=(panel,)
        )
    if node is None:
        return "", []
    rows = _rows(node.get("draw_header", []), node["label"]) + _rows(
        node.get("draw_header_preset", [])
    )
    rows += _rows(node.get("draw", []))
    shown_as = next(
        (item["text"] for item in node.get("draw", []) if item.get("kind") == "menu"),
        "",
    )
    return shown_as, rows


def _section(panel: str, active: str, overrides: Dict[str, str], variants) -> List[str]:
    cls = getattr(bpy.types, panel)
    order: List[tuple] = []
    seen: Dict[tuple, List[str]] = {}
    labels: List[str] = []
    menu_choices: Dict[tuple, List[str]] = {}
    for label, setup in variants:
        shown_as, rows = _record(panel, active, overrides, setup)
        name = shown_as if label is None else label.format(shown_as)
        if not rows:
            continue
        labels.append(name)
        merged = []
        for kind, item, tip in rows:
            if kind == "menu":
                tip, _, chosen = tip.partition("\0")
                key = ("menu", item, tip)
                if chosen != item:
                    menu_choices.setdefault(key, [])
                    if chosen not in menu_choices[key]:
                        menu_choices[key].append(chosen)
                merged.append(key)
            else:
                merged.append((kind, item, tip))
        for row in merged:
            if row not in seen:
                seen[row] = []
                order.append(row)
            if name not in seen[row]:
                seen[row].append(name)
    title = cls.bl_label or panel.replace("XPLANE_PT_", "").replace("_", " ").title()
    lines = ["", f"### {title}", ""]
    if not order:
        return lines + ["Nothing to set here in the demo scene."]
    several = len([label for label in labels if label]) > 1
    lines += ["| Name | Kind | Shown for | What it does |", "|---|---|---|---|"]
    for row in order:
        kind, name, tip = row
        if len(menu_choices.get(row, [])) > 1:
            tip = (
                (tip + " " if tip else "")
                + "Choices: "
                + ", ".join(menu_choices[row])
                + "."
            )
        shown = _shown(seen[row], labels) if several else ""
        lines.append(f"| {_cell(name)} | {kind} | {_cell(shown)} | {_cell(tip)} |")
    return lines


# Where a menu opens, for the ones that share their title
MENU_TITLES = {
    "XPLANE_MT_add": "Add (Shift+A) > X-Plane",
    "XPLANE_MT_object_context": "Right-click > X-Plane",
    "XPLANE_MT_pie": "X-Plane Pie Menu (Shift+Q)",
}


def _menus() -> List[str]:
    import scenes
    import ui_recorder

    scenes.build()
    obj = scenes.select("glareshield panel")
    context = {"object": obj, "active_object": obj, **shots.view_context()}
    lines = ["", "## Menus"]
    names = sorted(
        name
        for name in dir(bpy.types)
        if name.startswith("XPLANE_MT_")
        and getattr(getattr(bpy.types, name), "__module__", "").startswith(
            "io_xplane2blender"
        )
    )
    for name in names:
        cls = getattr(bpy.types, name)
        node = ui_recorder.record_menu(cls, context)
        rows = _rows(node["draw"])
        lines += ["", f"### {MENU_TITLES.get(name, cls.bl_label)}", ""]
        if not rows:
            lines.append("Filled in from the scene (the export files, for example).")
            continue
        lines += ["| Item | Kind | What it does |", "|---|---|---|"]
        lines += [
            f"| {_cell(item)} | {kind} | {_cell(tip.partition(chr(0))[0])} |"
            for kind, item, tip in rows
        ]
    return lines


# What the add-on adds to Blender's own menus and panels, and where
ENTRIES = (
    ("File > Export", "io_xplane2blender.menu_func"),
    ("File > Import", "io_xplane2blender.xplane_importer.ops.menu_func_import"),
    ("Add (Shift+A)", "io_xplane2blender.ui.menus.add_menu_entry"),
    (
        "Right-click menu of the 3D View",
        "io_xplane2blender.ui.menus.context_menu_entry",
    ),
    (
        "Overlays popover of the 3D View",
        "io_xplane2blender.viewport.overlay.overlay_popover",
    ),
    (
        "Workspace tabs' right-click menu",
        "io_xplane2blender.viewport.workspace.workspace_menu_entry",
    ),
)


def _entries() -> List[str]:
    import importlib

    import scenes
    import ui_recorder

    scenes.build()
    obj = scenes.select("glareshield panel")
    context = {"object": obj, "active_object": obj, **shots.view_context()}
    lines = [
        "",
        "## In Blender's Own Menus",
        "",
        "| Where | Item | Kind | What it does |",
        "|---|---|---|---|",
    ]
    for where, path in ENTRIES:
        module, _, name = path.rpartition(".")
        node = ui_recorder.record_function(
            getattr(importlib.import_module(module), name), context
        )
        for kind, item, tip in _rows(node["draw"]):
            lines.append(
                f"| {_cell(where)} | {_cell(item)} | {kind} | {_cell(tip.partition(chr(0))[0])} |"
            )
    return lines


# Operators that draw their own options, and where they are seen
OPTIONS = (
    (
        "File > Import > X-Plane Aircraft (.acf)",
        "io_xplane2blender.xplane_importer.ops.IMPORT_OT_xplane_aircraft",
    ),
    (
        "File > Import > X-Plane Object (.obj)",
        "io_xplane2blender.xplane_importer.ops.IMPORT_OT_xplane_obj",
    ),
)


def _options() -> List[str]:
    import ui_recorder

    lines = [
        "",
        "## Import Options",
        "",
        "The options in the side panel of the file browser.",
        "",
    ]
    lines += ["| Where | Option | What it does |", "|---|---|---|"]
    import importlib

    for where, path in OPTIONS:
        module, _, name = path.rpartition(".")
        node = ui_recorder.record_operator(
            getattr(importlib.import_module(module), name), {}
        )
        for kind, item, tip in _rows(node["draw"]):
            lines.append(f"| {_cell(where)} | {_cell(item)} | {_cell(tip)} |")
    return lines


def markdown() -> str:
    lines = [HEADER.rstrip()]
    tab = None
    for section_tab, panel, active, overrides, variants in _sections():
        if section_tab != tab:
            lines += ["", f"## {section_tab}"]
            tab = section_tab
        lines += _section(panel, active, overrides, variants)
    lines += _entries()
    lines += _options()
    lines += _menus()
    return "\n".join(lines) + "\n"


def main() -> None:
    sys.path[:0] = [REPO, TOOLS]
    import io_xplane2blender

    io_xplane2blender.register()
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(markdown())
    print("WROTE", PAGE)


if __name__ == "__main__":
    main()
