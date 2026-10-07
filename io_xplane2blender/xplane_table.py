"""
Tables of the X-Plane settings of many objects: manipulators, light levels and animation datarefs.

A cockpit has hundreds of each, and the properties editor shows one object at a time. The table lists them all
in the 3D viewport's sidebar, editable in place, and CSV export and import lets them be reviewed and edited in a
spreadsheet: sort by command, fill a column, compare with a systems list, then read it back.

The CSV columns come from the add-on's own property definitions, so every setting is covered. Keyframes stay in
Blender: the animation table holds the dataref paths and show/hide values, not the animation itself.
"""

import csv
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import bpy
from bpy_extras.io_utils import ExportHelper, ImportHelper

TABLES = (
    ("MANIPULATORS", "Manipulators", "Objects with a manipulator"),
    ("LIGHT_LEVELS", "Light Levels", "Objects with a light level"),
    ("ANIMATIONS", "Animations", "Animation datarefs of objects (paths and show/hide values, not keyframes)"),
)

# Which manipulator setting is the one to show in the table, by manipulator type
SINGLE_COMMAND_TYPES = {"command", "command_knob2", "command_switch_up_down2", "command_switch_left_right2"}
TWO_COMMAND_TYPES = {"command_axis", "command_knob", "command_switch_up_down", "command_switch_left_right"}

LIGHT_LEVEL_COLUMNS = (
    "lightLevel",
    "lightLevel_v1",
    "lightLevel_v2",
    "lightLevel_dataref",
    "lightLevel_photometric",
    "lightLevel_brightness",
)
SIMPLE_TYPES = {"STRING", "ENUM", "FLOAT", "INT", "BOOLEAN"}
# Not settings: the property group's own name, and the dataref value that keyframes drive
SKIPPED = {"rna_type", "name", "value"}


def simple_properties(struct) -> List[str]:
    """The single value settings of a property group, in their defined order"""
    return [
        p.identifier
        for p in struct.bl_rna.properties
        if p.type in SIMPLE_TYPES
        and p.identifier not in SKIPPED
        and not getattr(p, "is_array", False)
        and not (p.type == "ENUM" and p.is_enum_flag)
    ]


def has_feature(obj: bpy.types.Object, table: str) -> bool:
    if table == "MANIPULATORS":
        return obj.xplane.manip.enabled
    if table == "LIGHT_LEVELS":
        return obj.xplane.lightLevel
    return len(obj.xplane.datarefs) > 0


def main_manip_setting(manip) -> str:
    if manip.type in SINGLE_COMMAND_TYPES:
        return "command"
    if manip.type in TWO_COMMAND_TYPES:
        return "positive_command"
    return "dataref1"


def searchable_texts(obj: bpy.types.Object, table: str) -> Iterable[str]:
    """What the table's search box also looks in, besides the object name"""
    if table == "MANIPULATORS":
        m = obj.xplane.manip
        return (m.command, m.positive_command, m.negative_command, m.dataref1, m.dataref2, m.tooltip)
    if table == "LIGHT_LEVELS":
        return (obj.xplane.lightLevel_dataref,)
    return [d.path for d in obj.xplane.datarefs]


def tail(text: str, length: int = 22) -> str:
    """The end of a long dataref or command, where 'key/A' and 'key/B' differ"""
    return text if len(text) <= length else "…" + text[-(length - 1):]


def format_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(round(value, 6))
    return str(value)


def parse_value(prop: bpy.types.Property, text: str):
    """Raises ValueError for a value the setting cannot take"""
    text = text.strip()
    if prop.type == "BOOLEAN":
        lowered = text.lower()
        if lowered in ("true", "1", "yes", "on", "x"):
            return True
        if lowered in ("false", "0", "no", "off", ""):
            return False
        raise ValueError(f"'{text}' is not true or false")
    if prop.type == "INT":
        return int(float(text))
    if prop.type == "FLOAT":
        return float(text.replace(",", "."))
    return text


def header(table: str, sample: bpy.types.Object) -> List[str]:
    if table == "MANIPULATORS":
        return ["object"] + simple_properties(sample.xplane.manip)
    if table == "LIGHT_LEVELS":
        return ["object", *LIGHT_LEVEL_COLUMNS]
    dataref = sample.xplane.datarefs.add()
    columns = ["object", "index"] + simple_properties(dataref)
    sample.xplane.datarefs.remove(len(sample.xplane.datarefs) - 1)
    return columns


def rows(objects: Sequence[bpy.types.Object], table: str) -> List[Dict[str, str]]:
    out = []
    for obj in sorted((o for o in objects if has_feature(o, table)), key=lambda o: o.name):
        if table == "MANIPULATORS":
            m = obj.xplane.manip
            out.append({"object": obj.name, **{c: format_value(getattr(m, c)) for c in simple_properties(m)}})
        elif table == "LIGHT_LEVELS":
            x = obj.xplane
            out.append({"object": obj.name, **{c: format_value(getattr(x, c)) for c in LIGHT_LEVEL_COLUMNS}})
        else:
            for i, d in enumerate(obj.xplane.datarefs):
                out.append(
                    {"object": obj.name, "index": str(i), **{c: format_value(getattr(d, c)) for c in simple_properties(d)}}
                )
    return out


def write_csv(path: str, objects: Sequence[bpy.types.Object], table: str) -> int:
    """Writes the table and returns the number of rows"""
    # The columns of an empty table still come from a real object's settings
    sample = bpy.data.objects.new("__xplane_table_sample__", None)
    try:
        columns = header(table, sample)
    finally:
        bpy.data.objects.remove(sample)
    table_rows = rows(objects, table)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(table_rows)
    return len(table_rows)


@dataclass
class ImportResult:
    changed: int = 0
    objects: set = field(default_factory=set)
    unknown_objects: List[str] = field(default_factory=list)
    unknown_columns: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    def summary(self) -> str:
        text = f"Changed {self.changed} setting(s) on {len(self.objects)} object(s)"
        if self.unknown_objects:
            names = ", ".join(self.unknown_objects[:3]) + ("..." if len(self.unknown_objects) > 3 else "")
            text += f"; {len(self.unknown_objects)} object(s) not found ({names})"
        if self.unknown_columns:
            text += f"; ignored column(s): {', '.join(self.unknown_columns)}"
        if self.problems:
            text += f"; {len(self.problems)} value(s) could not be used: {self.problems[0]}"
        return text


def _set(result: ImportResult, obj, owner, column: str, text: str, row_number: int) -> None:
    prop = owner.bl_rna.properties[column]
    try:
        value = parse_value(prop, text)
        if prop.type == "FLOAT" and abs(getattr(owner, column) - value) < 1e-7:
            return
        if getattr(owner, column) == value:
            return
        setattr(owner, column, value)
    except (ValueError, TypeError) as e:
        result.problems.append(f"row {row_number}, {column}: {e}")
        return
    result.changed += 1
    result.objects.add(obj.name)


def read_csv(path: str, table: str, scene: bpy.types.Scene) -> ImportResult:
    """Applies a table's values to the objects of the scene, by object name. Values that are already the same are
    not counted, objects that are not found and values that cannot be used are reported, nothing else is touched"""
    result = ImportResult()
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        sample = bpy.data.objects.new("__xplane_table_sample__", None)
        try:
            known = set(header(table, sample))
        finally:
            bpy.data.objects.remove(sample)
        result.unknown_columns = [c for c in columns if c not in known]
        used = [c for c in columns if c in known and c not in ("object", "index")]
        for row_number, row in enumerate(reader, start=2):
            name = (row.get("object") or "").strip()
            obj = scene.objects.get(name)
            if obj is None:
                if name and name not in result.unknown_objects:
                    result.unknown_objects.append(name)
                continue
            if table == "MANIPULATORS":
                owner = obj.xplane.manip
            elif table == "LIGHT_LEVELS":
                owner = obj.xplane
            else:
                try:
                    index = int(row.get("index") or 0)
                except ValueError:
                    result.problems.append(f"row {row_number}, index: '{row.get('index')}' is not a number")
                    continue
                if index < 0:
                    result.problems.append(f"row {row_number}, index: must not be negative")
                    continue
                while len(obj.xplane.datarefs) <= index:
                    obj.xplane.datarefs.add()
                owner = obj.xplane.datarefs[index]
            for column in used:
                if row.get(column) is not None:
                    _set(result, obj, owner, column, row[column], row_number)
    return result


# ---- Blender UI -----------------------------------------------------------------------------------------------


def _select_from_table(self, context):
    """Clicking a row selects that object, so the table doubles as a way to find a control in the cockpit"""
    objects = bpy.data.objects
    if not 0 <= self.index < len(objects):
        return
    obj = objects[self.index]
    if context.view_layer.objects.get(obj.name) is None:
        return
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class XPlaneTableSettings(bpy.types.PropertyGroup):
    table: bpy.props.EnumProperty(name="Table", items=TABLES, default="MANIPULATORS")
    selected_only: bpy.props.BoolProperty(
        name="Selected Only", description="List only the selected objects", default=False
    )
    index: bpy.props.IntProperty(update=_select_from_table)


def table_settings(context) -> XPlaneTableSettings:
    return context.window_manager.xplane_table


def table_objects(context) -> List[bpy.types.Object]:
    s = table_settings(context)
    objects = context.selected_objects if s.selected_only else context.scene.objects
    return [o for o in objects if has_feature(o, s.table)]


class XPLANE_UL_object_table(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        obj = item
        table = table_settings(context).table
        x = obj.xplane
        # The sidebar is narrow until it is dragged wider, so the columns that matter most come first
        width = context.region.width / max(context.preferences.system.ui_scale, 0.5)
        wide, medium = width > 640, width > 400
        # Characters that fit in the text column when it is too narrow to edit, about 9 pixels each
        fits = max(8, int(width * 0.45 / 9))
        split = layout.split(factor=0.3 if medium else 0.42, align=True)
        split.label(text=obj.name, icon="OBJECT_DATA")
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
        else:
            row = split.row(align=True)
            if medium:
                row.prop(x.datarefs[0], "path", text="")
            else:
                row.label(text=tail(x.datarefs[0].path, fits))
            if len(x.datarefs) > 1:
                row.label(text=f"+{len(x.datarefs) - 1}")

    def filter_items(self, context, data, propname):
        objects = getattr(data, propname)
        s = table_settings(context)
        in_scene = context.scene.objects
        selected = set(context.selected_objects) if s.selected_only else None
        text = self.filter_name.lower()
        flags = []
        for obj in objects:
            show = in_scene.get(obj.name) is obj and has_feature(obj, s.table)
            if show and selected is not None:
                show = obj in selected
            if show and text:
                show = text in obj.name.lower() or any(text in t.lower() for t in searchable_texts(obj, s.table))
            if self.use_filter_invert and text:
                show = not show and in_scene.get(obj.name) is obj and has_feature(obj, s.table)
            flags.append(self.bitflag_filter_item if show else 0)
        order = bpy.types.UI_UL_list.sort_items_by_name(objects, "name")
        return flags, order


class XPLANE_OT_table_export_csv(bpy.types.Operator, ExportHelper):
    """Save the table as a CSV file for a spreadsheet"""

    bl_idname = "xplane.table_export_csv"
    bl_label = "Export CSV"
    filename_ext = ".csv"
    filter_glob: bpy.props.StringProperty(default="*.csv", options={"HIDDEN"})

    def execute(self, context):
        s = table_settings(context)
        objects = context.selected_objects if s.selected_only else list(context.scene.objects)
        count = write_csv(self.filepath, objects, s.table)
        self.report({"INFO"}, f"Wrote {count} row(s) to {bpy.path.basename(self.filepath)}")
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
            self.report({"ERROR"}, f"Could not read {bpy.path.basename(self.filepath)}: {e}")
            return {"CANCELLED"}
        problems = result.unknown_objects or result.problems or result.unknown_columns
        self.report({"WARNING"} if problems else {"INFO"}, result.summary())
        return {"FINISHED"}


class VIEW3D_PT_xplane_table(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "X-Plane"
    bl_label = "Table"
    bl_parent_id = "XPLANE_PT_tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = table_settings(context)
        layout = self.layout
        layout.row().prop(s, "table", expand=True)
        row = layout.row()
        row.prop(s, "selected_only")
        row.label(text=f"{len(table_objects(context))} object(s)")
        layout.template_list("XPLANE_UL_object_table", "", bpy.data, "objects", s, "index", rows=12)
        row = layout.row(align=True)
        row.operator(XPLANE_OT_table_export_csv.bl_idname, icon="EXPORT")
        row.operator(XPLANE_OT_table_import_csv.bl_idname, icon="IMPORT")


_classes = (
    XPlaneTableSettings,
    XPLANE_UL_object_table,
    XPLANE_OT_table_export_csv,
    XPLANE_OT_table_import_csv,
    VIEW3D_PT_xplane_table,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.xplane_table = bpy.props.PointerProperty(type=XPlaneTableSettings)


def unregister():
    del bpy.types.WindowManager.xplane_table
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
