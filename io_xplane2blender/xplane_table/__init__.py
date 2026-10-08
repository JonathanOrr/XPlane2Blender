"""
Tables of the X-Plane settings of many objects: clickable objects, glows, datarefs and lights, in the Scene tab and
as CSV files for a spreadsheet. rows.py has the data and the CSV, view.py the panel.
"""

import bpy

from . import view
from .rows import (  # noqa: F401
    TABLES,
    ImportResult,
    format_value,
    has_feature,
    header,
    main_manip_setting,
    owner_of,
    parse_value,
    read_csv,
    rows,
    searchable_texts,
    simple_properties,
    tail,
    write_csv,
)
from .view import (  # noqa: F401
    XPlaneTableSettings,
    table_count,
    table_objects,
    table_settings,
)


def register():
    for cls in view.classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.xplane_table = bpy.props.PointerProperty(
        type=view.XPlaneTableSettings
    )


def unregister():
    del bpy.types.WindowManager.xplane_table
    for cls in reversed(view.classes):
        bpy.utils.unregister_class(cls)
