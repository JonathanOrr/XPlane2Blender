"""
The rows of the tables and how they go to and from a spreadsheet.

A cockpit has hundreds of manipulators, light levels, datarefs and lights, and the Properties editor shows one
object at a time. The tables list them all, editable in place, and CSV export and import lets them be reviewed and
edited in a spreadsheet: sort by command, fill a column, compare with a systems list, then read it back.

The CSV columns come from the add-on's own property definitions, so every setting is covered. Keyframes stay in
Blender: the datarefs table holds the dataref paths and show/hide values, not the animation itself.
"""

import csv
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

import bpy

# (identifier, name, description). The names are the ones of the Object tab's cards
TABLES = (
    ("MANIPULATORS", "Clickable", "Objects that can be clicked in the cockpit"),
    ("LIGHT_LEVELS", "Glow", "Objects whose night texture glows with a dataref"),
    (
        "ANIMATIONS",
        "Datarefs",
        "The datarefs that move, show or hide objects (paths and values, not keyframes)",
    ),
    ("LIGHTS", "Lights", "Every light and which X-Plane light it becomes"),
)

# Which manipulator setting is the one to show in the table, by manipulator type
SINGLE_COMMAND_TYPES = {
    "command",
    "command_knob2",
    "command_switch_up_down2",
    "command_switch_left_right2",
}
TWO_COMMAND_TYPES = {
    "command_axis",
    "command_knob",
    "command_switch_up_down",
    "command_switch_left_right",
}

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
SAMPLE_NAME = "__xplane_table_sample__"


def simple_properties(struct, keep_name: bool = False) -> List[str]:
    """The single value settings of a property group, in their defined order"""
    return [
        p.identifier
        for p in struct.bl_rna.properties
        if p.type in SIMPLE_TYPES
        and (p.identifier not in SKIPPED or (keep_name and p.identifier == "name"))
        and not getattr(p, "is_array", False)
        and not (p.type == "ENUM" and p.is_enum_flag)
    ]


def has_feature(obj: bpy.types.Object, table: str) -> bool:
    if table == "MANIPULATORS":
        return obj.xplane.manip.enabled
    if table == "LIGHT_LEVELS":
        return obj.xplane.lightLevel
    if table == "LIGHTS":
        return obj.type == "LIGHT"
    return len(obj.xplane.datarefs) > 0


def owner_of(obj: bpy.types.Object, table: str):
    """The property group of the object a row of the table edits (not the datarefs, which have one group per row)"""
    if table == "MANIPULATORS":
        return obj.xplane.manip
    if table == "LIGHT_LEVELS":
        return obj.xplane
    if table == "LIGHTS":
        return obj.data.xplane if obj.type == "LIGHT" else None
    return None


def main_manip_setting(manip) -> str:
    if manip.type in SINGLE_COMMAND_TYPES:
        return "command"
    if manip.type in TWO_COMMAND_TYPES:
        return "positive_command"
    if manip.type == "device":
        return "plugin_device" if manip.device_name == "Plugin Device" else "device_name"
    return "dataref1"


def searchable_texts(obj: bpy.types.Object, table: str) -> Iterable[str]:
    """What the table's search box also looks in, besides the object name"""
    if table == "MANIPULATORS":
        m = obj.xplane.manip
        return (
            m.command,
            m.positive_command,
            m.negative_command,
            m.dataref1,
            m.dataref2,
            m.tooltip,
            m.device_name if m.type == "device" else "",
            m.plugin_device,
        )
    if table == "LIGHT_LEVELS":
        return (obj.xplane.lightLevel_dataref,)
    if table == "LIGHTS":
        x = obj.data.xplane
        return (x.name, x.params, x.dataref)
    return [d.path for d in obj.xplane.datarefs]


def tail(text: str, length: int = 22) -> str:
    """The end of a long dataref or command, where 'key/A' and 'key/B' differ"""
    return text if len(text) <= length else "…" + text[-(length - 1) :]


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


@contextmanager
def sample_object(table: str) -> Iterator[bpy.types.Object]:
    """A throwaway object of the kind the table lists, to read the settings' definitions from"""
    data = bpy.data.lights.new(SAMPLE_NAME, "POINT") if table == "LIGHTS" else None
    obj = bpy.data.objects.new(SAMPLE_NAME, data)
    try:
        yield obj
    finally:
        bpy.data.objects.remove(obj)
        if data is not None:
            bpy.data.lights.remove(data)


def columns_of(table: str, owner) -> List[str]:
    """The settings of a table's property group that are columns. A light's own name is a setting, its lights.txt name"""
    if table == "LIGHT_LEVELS":
        return list(LIGHT_LEVEL_COLUMNS)
    return simple_properties(owner, keep_name=table == "LIGHTS")


def header(table: str) -> List[str]:
    with sample_object(table) as sample:
        if table != "ANIMATIONS":
            return ["object"] + columns_of(table, owner_of(sample, table))
        dataref = sample.xplane.datarefs.add()
        return ["object", "index"] + simple_properties(dataref)


def rows(objects: Sequence[bpy.types.Object], table: str) -> List[Dict[str, str]]:
    out = []
    columns: Optional[List[str]] = None
    for obj in sorted(
        (o for o in objects if has_feature(o, table)), key=lambda o: o.name
    ):
        if table == "ANIMATIONS":
            for i, d in enumerate(obj.xplane.datarefs):
                columns = columns or simple_properties(d)
                out.append(
                    {
                        "object": obj.name,
                        "index": str(i),
                        **{c: format_value(getattr(d, c)) for c in columns},
                    }
                )
            continue
        owner = owner_of(obj, table)
        if columns is None:
            columns = columns_of(table, owner)
        out.append(
            {
                "object": obj.name,
                **{c: format_value(getattr(owner, c)) for c in columns},
            }
        )
    return out


def write_csv(path: str, objects: Sequence[bpy.types.Object], table: str) -> int:
    """Writes the table and returns the number of rows"""
    # The columns of an empty table still come from a real object's settings
    columns = header(table)
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
            names = ", ".join(self.unknown_objects[:3]) + (
                "..." if len(self.unknown_objects) > 3 else ""
            )
            text += f"; {len(self.unknown_objects)} object(s) not found ({names})"
        if self.unknown_columns:
            text += f"; ignored column(s): {', '.join(self.unknown_columns)}"
        if self.problems:
            text += (
                f"; {len(self.problems)} value(s) could not be used: {self.problems[0]}"
            )
        return text


def _set(
    result: ImportResult, obj, owner, column: str, text: str, row_number: int
) -> None:
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


def _datarefs_owner(result: ImportResult, obj, row, row_number: int):
    """The dataref a row of the datarefs table is about, added when the file has more rows than the object has"""
    try:
        index = int(row.get("index") or 0)
    except ValueError:
        result.problems.append(
            f"row {row_number}, index: '{row.get('index')}' is not a number"
        )
        return None
    if index < 0:
        result.problems.append(f"row {row_number}, index: must not be negative")
        return None
    while len(obj.xplane.datarefs) <= index:
        obj.xplane.datarefs.add()
    return obj.xplane.datarefs[index]


def read_csv(path: str, table: str, scene: bpy.types.Scene) -> ImportResult:
    """Applies a table's values to the objects of the scene, by object name. Values that are already the same are
    not counted, objects that are not found and values that cannot be used are reported, nothing else is touched
    """
    result = ImportResult()
    # One lookup table: asking the scene for each name in turn is slow when it holds thousands of objects
    by_name = {o.name: o for o in scene.objects}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        known = set(header(table))
        result.unknown_columns = [c for c in columns if c not in known]
        used = [c for c in columns if c in known and c not in ("object", "index")]
        for row_number, row in enumerate(reader, start=2):
            name = (row.get("object") or "").strip()
            obj = by_name.get(name)
            if obj is None:
                if name and name not in result.unknown_objects:
                    result.unknown_objects.append(name)
                continue
            if table == "ANIMATIONS":
                owner = _datarefs_owner(result, obj, row, row_number)
            else:
                owner = owner_of(obj, table)
                if owner is None:
                    result.problems.append(f"row {row_number}: {name} is not a light")
            if owner is None:
                continue
            for column in used:
                if row.get(column) is not None:
                    _set(result, obj, owner, column, row[column], row_number)
    return result
