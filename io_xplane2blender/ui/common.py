"""
Drawing helpers shared by the panels of every tab.
"""

import bpy

from io_xplane2blender.xplane_properties_panel import (  # noqa: F401
    Properties,
    compact_grid,
    compact_row,
    named,
    switched,
)

from .search import text_with_search
from .state import resolve


def _line_width(icon: str) -> int:
    """About how many characters fit across the panel"""
    region = bpy.context.region
    if region is None or region.width < 50:
        return 44
    scale = bpy.context.preferences.system.ui_scale or 1.0
    return max(16, int(region.width / (7.0 * scale)) - (6 if icon != "NONE" else 3))


def wrapped(layout, text: str, icon: str = "NONE") -> None:
    """Labels do not wrap, so long text is cut into lines that fit"""
    width = _line_width(icon)
    line, first = "", True
    col = layout.column(align=True)
    for word in text.split():
        if line and len(line) + len(word) + 1 > width:
            col.label(text=line, icon=icon if first else "BLANK1")
            line, first = word, False
        else:
            line = f"{line} {word}".strip()
    if line:
        col.label(text=line, icon=icon if first else ("BLANK1" if icon != "NONE" else "NONE"))


class XPLANE_OT_list_add(bpy.types.Operator):
    """Add an entry"""

    bl_idname = "xplane.list_add"
    bl_label = "Add"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    target: bpy.props.StringProperty(options={"HIDDEN"})

    @classmethod
    def description(cls, context, properties):
        what = properties.target.rpartition(".")[2]
        return {
            "customAttributes": "Add an OBJ line typed by hand, for anything without a setting of its own",
            "customAnimAttributes": "Add an OBJ line typed by hand that is written with the object's animation",
            "axis_detent_ranges": "Add a detent: a range where the lever moves freely, and how high it is lifted to get in",
        }.get(what, "Add an entry")

    def execute(self, context):
        owner, attr = resolve(context, self.target)
        if owner is None:
            return {"CANCELLED"}
        getattr(owner, attr).add()
        return {"FINISHED"}


class XPLANE_OT_list_remove(bpy.types.Operator):
    """Remove this entry"""

    bl_idname = "xplane.list_remove"
    bl_label = "Remove"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    target: bpy.props.StringProperty(options={"HIDDEN"})
    index: bpy.props.IntProperty(options={"HIDDEN"})

    def execute(self, context):
        owner, attr = resolve(context, self.target)
        if owner is None or not 0 <= self.index < len(getattr(owner, attr)):
            return {"CANCELLED"}
        getattr(owner, attr).remove(self.index)
        return {"FINISHED"}


def add_button(layout, target: str, text: str) -> None:
    layout.operator(XPLANE_OT_list_add.bl_idname, text=text, icon="ADD").target = target


def remove_button(layout, target: str, index: int) -> None:
    op = layout.operator(XPLANE_OT_list_remove.bl_idname, text="", icon="X", emboss=False)
    op.target, op.index = target, index


def custom_lines_layout(layout, settings, target: str, animation: bool = True, reset: bool = True) -> None:
    """
    OBJ lines typed by hand, for anything without a setting of its own. target is where settings is,
    such as 'object:xplane'.
    """
    col = layout.column()
    col.label(text="Extra OBJ Lines")
    for i, attr in enumerate(settings.customAttributes):
        box = col.box().column(align=True)
        row = box.row(align=True)
        row.prop(attr, "name", text="")
        row.prop(attr, "value", text="")
        remove_button(row, f"{target}.customAttributes", i)
        if reset:
            row = compact_row(box)
            row.prop(attr, "reset", text="Undone By")
            row.prop(attr, "weight", text="Order")
    add_button(col, f"{target}.customAttributes", "Add Line")
    if not animation:
        return
    for i, attr in enumerate(settings.customAnimAttributes):
        box = col.box().column(align=True)
        row = box.row(align=True)
        row.prop(attr, "name", text="")
        row.prop(attr, "value", text="")
        remove_button(row, f"{target}.customAnimAttributes", i)
        box.prop(attr, "weight", text="Order")
    add_button(col, f"{target}.customAnimAttributes", "Add Animation Line")


def glow_layout(layout, settings, target: str) -> None:
    """The light level settings of an object or material: the night texture follows a dataref"""
    layout.active = settings.lightLevel
    wrapped(layout, "The night (LIT) texture's brightness follows a dataref, like a backlight on a dimmer.")
    text_with_search(layout, settings, "lightLevel_dataref", "Dataref", "dataref", target)
    col = layout.column(align=True)
    col.prop(settings, "lightLevel_v1", text="Off At")
    col.prop(settings, "lightLevel_v2", text="Full At")
    switched(layout, settings, "lightLevel_photometric", "lightLevel_brightness", "Full (nits)")


def copy_button(layout, context, what: str) -> None:
    if len(context.selected_objects) > 1:
        layout.operator("xplane.copy_to_selected", text="", icon="DUPLICATE", emboss=False).what = what


classes = (XPLANE_OT_list_add, XPLANE_OT_list_remove)
