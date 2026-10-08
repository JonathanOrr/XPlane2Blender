"""
The Table panel of the Scene tab: the objects of one table in a list, editable in place, and CSV export and import.

A production aircraft has thousands of objects, so the list works from what was found the last time instead of
looking at every object on every redraw (Blender redraws the panel whenever the mouse moves over a button).
What was found is kept until the scene changes, or for a second.
"""

import csv
from typing import List, Tuple

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_scene_changes as changes
from io_xplane2blender.xplane_properties_panel import Properties, compact_row
from io_xplane2blender.xplane_scene_changes import Remembered

from .rows import (
    TABLES,
    has_feature,
    main_manip_setting,
    read_csv,
    searchable_texts,
    tail,
    write_csv,
)

LIGHT_NAMED_TYPES = (C.LIGHT_NAMED, C.LIGHT_AUTOMATIC, C.LIGHT_PARAM)

_found = Remembered()
_listed = Remembered()
# The positions the list showed the last time it looked, for Select Listed
_last_listed: List[int] = []


_positions = Remembered()


def _position_of(context, obj: bpy.types.Object) -> int:
    """Where an object is in the scene's objects, or -1 when the table does not list it"""
    entries = _found_entries(context, context.scene.objects)
    positions = _positions.get((_found.version,), lambda: {o: i for i, o in entries})
    return positions.get(obj, -1)


def _active_row(self) -> int:
    """The list marks the row of the active object, so it shows which of the objects the viewport has picked"""
    context = bpy.context
    active = context.view_layer.objects.active if context.view_layer else None
    return -1 if active is None else _position_of(context, active)


def _select_row(self, row: int) -> None:
    """Clicking a row selects that object, so the table doubles as a way to find a control in the cockpit"""
    context = bpy.context
    objects = context.scene.objects
    if not 0 <= row < len(objects):
        return
    obj = objects[row]
    if context.view_layer.objects.get(obj.name) is None:
        return
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class XPlaneTableSettings(bpy.types.PropertyGroup):
    table: bpy.props.EnumProperty(name="Table", items=TABLES, default="MANIPULATORS")
    selected_only: bpy.props.BoolProperty(
        name="Selected Only",
        description="List only the selected objects",
        default=False,
    )
    index: bpy.props.IntProperty(get=_active_row, set=_select_row)


def table_settings(context) -> XPlaneTableSettings:
    return context.window_manager.xplane_table


def _found_entries(context, objects) -> List[Tuple[int, bpy.types.Object]]:
    """(position in the scene's objects, object) of everything the table lists, before the search box is applied"""
    s = table_settings(context)
    key = (
        s.table,
        s.selected_only,
        context.scene.as_pointer(),
        len(objects),
        changes.count(),
    )

    def make():
        selected = set(context.selected_objects) if s.selected_only else None
        return [
            (i, o)
            for i, o in enumerate(objects)
            if has_feature(o, s.table) and (selected is None or o in selected)
        ]

    return _found.get(key, make)


def table_objects(context) -> List[bpy.types.Object]:
    return [o for _, o in _found_entries(context, context.scene.objects)]


def table_count(context) -> int:
    return len(_found_entries(context, context.scene.objects))


def _matches(obj: bpy.types.Object, table: str, needle: str) -> bool:
    return (
        not needle
        or needle in obj.name.lower()
        or any(needle in t.lower() for t in searchable_texts(obj, table))
    )


def _listed_positions(context, entries, text: str, invert: bool) -> List[int]:
    """The positions of the objects to list, in the order to list them: by name"""
    table = table_settings(context).table
    needle = text.lower()
    # Inverting only means something with text to search for
    flip = invert and bool(needle)
    shown = [
        (o.name.lower(), i) for i, o in entries if _matches(o, table, needle) != flip
    ]
    shown.sort()
    return [i for _, i in shown]


def filter_and_order(context, objects, text: str, invert: bool, bit: int):
    """What UIList.filter_items returns: a flag for each of the scene's objects and the order of them"""
    try:
        return _filter_and_order(context, objects, text, invert, bit)
    except ReferenceError:
        # An undo took away the objects that were found: look again
        _found.key = _listed.key = None
        return _filter_and_order(context, objects, text, invert, bit)


def _filter_and_order(context, objects, text: str, invert: bool, bit: int):
    entries = _found_entries(context, objects)
    key = (_found.version, text, invert, bit, len(objects))

    def make():
        positions = _listed_positions(context, entries, text, invert)
        _last_listed[:] = positions
        flags = [0] * len(objects)
        order = [0] * len(objects)
        for place, i in enumerate(positions):
            flags[i] = bit
            order[i] = place
        later = len(positions)
        for i, flag in enumerate(flags):
            if not flag:
                order[i] = later
                later += 1
        return flags, order

    return _listed.get(key, make)


def listed_objects(context) -> List[bpy.types.Object]:
    """The objects the list showed the last time it was drawn, the search box applied, in the order they are shown"""
    objects = context.scene.objects
    return [objects[i] for i in _last_listed if i < len(objects)]


# ---- Blender UI -----------------------------------------------------------------------------------------------


def _light_row(
    layout, obj: bpy.types.Object, medium: bool, wide: bool, fits: int
) -> None:
    light = obj.data
    x = light.xplane
    row = layout.row(align=True)
    if wide:
        row.prop(x, "type", text="")
    if x.type in LIGHT_NAMED_TYPES:
        if medium:
            row.prop(x, "name", text="")
        else:
            row.label(text=tail(x.name, fits))
        if wide and x.type == C.LIGHT_PARAM:
            row.prop(x, "params", text="")
    elif medium:
        row.prop(x, "dataref", text="")
    else:
        row.label(text=x.type.title())
    if medium and x.type != C.LIGHT_NON_EXPORTING:
        sub = row.row(align=True)
        sub.ui_units_x = 2.5
        sub.prop(light, "color", text="")


class XPLANE_UL_object_table(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        obj = item
        table = table_settings(context).table
        x = obj.xplane
        # A narrow Properties editor fits few columns, so the ones that matter most come first
        width = context.region.width / max(context.preferences.system.ui_scale, 0.5)
        wide, medium = width > 640, width > 400
        # Characters that fit in the text column when it is too narrow to edit, about 9 pixels each
        fits = max(8, int(width * 0.45 / 9))
        split = layout.split(factor=0.3 if medium else 0.42, align=True)
        split.label(
            text=obj.name, icon="LIGHT_DATA" if table == "LIGHTS" else "OBJECT_DATA"
        )
        if table == "MANIPULATORS":
            m = x.manip
            rest = split
            if wide:
                rest = split.split(factor=0.24, align=True)
                rest.prop(m, "type", text="")
            if medium:
                texts = rest.split(factor=0.62, align=True)
                texts.prop(m, main_manip_setting(m), text="")
                texts.prop(m, "tooltip", text="")
            else:
                # Too narrow to edit: show the end of the command, the part that tells two controls apart
                rest.label(text=tail(getattr(m, main_manip_setting(m)), fits))
        elif table == "LIGHT_LEVELS":
            rest = split
            if medium:
                rest = split.split(factor=0.36, align=True)
                values = rest.row(align=True)
                values.prop(x, "lightLevel_v1", text="")
                values.prop(x, "lightLevel_v2", text="")
                rest.prop(x, "lightLevel_dataref", text="")
            else:
                rest.label(text=tail(x.lightLevel_dataref, fits))
        elif table == "LIGHTS":
            _light_row(split, obj, medium, wide, fits)
        else:
            row = split.row(align=True)
            if medium:
                row.prop(x.datarefs[0], "path", text="")
            else:
                row.label(text=tail(x.datarefs[0].path, fits))
            if len(x.datarefs) > 1:
                row.label(text=f"+{len(x.datarefs) - 1}")

    def filter_items(self, context, data, propname):
        return filter_and_order(
            context,
            getattr(data, propname),
            self.filter_name,
            self.use_filter_invert,
            self.bitflag_filter_item,
        )


class XPLANE_OT_table_select_listed(bpy.types.Operator):
    """Select every object the list shows, the search box applied, to work on them together: copy settings,
    find and replace, hide or move them"""

    bl_idname = "xplane.table_select_listed"
    bl_label = "Select Listed"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        listed = listed_objects(context)
        for other in context.selected_objects:
            other.select_set(False)
        selected = []
        for obj in listed:
            try:
                obj.select_set(True)
            except RuntimeError:  # Hidden, or not in the view layer
                continue
            selected.append(obj)
        if selected:
            context.view_layer.objects.active = selected[0]
        left = len(listed) - len(selected)
        self.report(
            {"INFO"},
            f"Selected {len(selected)} object(s)" + (f", {left} hidden ones could not be" if left else ""),
        )
        return {"FINISHED"}


class XPLANE_OT_table_export_csv(bpy.types.Operator, ExportHelper):
    """Save the table as a CSV file for a spreadsheet"""

    bl_idname = "xplane.table_export_csv"
    bl_label = "Export CSV"
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        s = table_settings(context)
        objects = (
            context.selected_objects if s.selected_only else list(context.scene.objects)
        )
        count = write_csv(self.filepath, objects, s.table)
        self.report(
            {"INFO"}, f"Wrote {count} row(s) to {bpy.path.basename(self.filepath)}"
        )
        return {"FINISHED"}


class XPLANE_OT_table_import_csv(bpy.types.Operator, ImportHelper):
    """Read a CSV file and apply its values to the objects with the same names"""

    bl_idname = "xplane.table_import_csv"
    bl_label = "Import CSV"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        s = table_settings(context)
        try:
            result = read_csv(self.filepath, s.table, context.scene)
        except (OSError, csv.Error, UnicodeDecodeError) as e:
            self.report(
                {"ERROR"}, f"Could not read {bpy.path.basename(self.filepath)}: {e}"
            )
            return {"CANCELLED"}
        problems = result.unknown_objects or result.problems or result.unknown_columns
        self.report({"WARNING"} if problems else {"INFO"}, result.summary())
        return {"FINISHED"}


class XPLANE_PT_table(Properties, bpy.types.Panel):
    bl_context = "scene"
    bl_label = "X-Plane Tables"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = table_settings(context)
        layout = self.layout
        layout.row().prop(s, "table", expand=True)
        row = compact_row(layout, align=False)
        row.prop(s, "selected_only")
        row.label(text=f"{table_count(context)} object(s)")
        row.operator(XPLANE_OT_table_select_listed.bl_idname, icon="RESTRICT_SELECT_OFF")
        layout.template_list(
            "XPLANE_UL_object_table", "", context.scene, "objects", s, "index", rows=12
        )
        row = layout.row(align=True)
        row.operator(XPLANE_OT_table_export_csv.bl_idname, icon="EXPORT")
        row.operator(XPLANE_OT_table_import_csv.bl_idname, icon="IMPORT")


classes = (
    XPlaneTableSettings,
    XPLANE_UL_object_table,
    XPLANE_OT_table_select_listed,
    XPLANE_OT_table_export_csv,
    XPLANE_OT_table_import_csv,
    XPLANE_PT_table,
)
