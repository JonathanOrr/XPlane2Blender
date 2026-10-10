"""
Object tab: what the active object is in plain words, which file it exports in, what is unfinished, and a
card for each thing it can do.
"""

from typing import Dict

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I

from .common import (
    Properties,
    add_button,
    copy_button,
    custom_lines_layout,
    glow_layout,
    named,
    remove_button,
    switched,
    wrapped,
)
from .menus import XPLANE_MT_control_kind, XPLANE_MT_move_to_file
from .motion import draw_order_layout, motion_layout, visibility_layout
from .ops_file import XPLANE_OT_new_file, XPLANE_OT_show_file
from .search import text_with_search

ALL_TYPES = ("MESH", "LIGHT", "EMPTY", "ARMATURE")


class XPLANE_PT_object(Properties, bpy.types.Panel):
    bl_label = "X-Plane"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        scene = context.scene

        wrapped(layout, " · ".join(I.summary(obj)))
        selected = context.selected_objects
        if len(selected) > 1:
            counts: Dict[str, int] = {}
            for o in selected:
                word = I.summary(o)[0]
                counts[word] = counts.get(word, 0) + 1
            layout.label(
                text=f"{len(selected)} selected: " + ", ".join(f"{n} {w.lower()}" for w, n in sorted(counts.items())),
                icon="RESTRICT_SELECT_OFF",
            )

        owners = I.files_of(obj, scene)
        if obj.type not in ALL_TYPES:
            layout.label(text="X-Plane does not use this kind of object", icon="INFO")
        elif not owners:
            box = layout.box()
            box.label(text="Not exported: it is not in an export file", icon="ERROR")
            row = box.row(align=True)
            row.operator(XPLANE_OT_new_file.bl_idname, text="New File", icon="ADD")
            row.menu(XPLANE_MT_move_to_file.bl_idname, text="Move To File")
        else:
            row = layout.row(align=True)
            for owner in owners:
                if isinstance(owner, bpy.types.Collection):
                    text = f"In {I.file_name(owner)}"
                    row.operator(XPLANE_OT_show_file.bl_idname, text=text, icon="FILE").collection = owner.name
                else:
                    row.label(text=f"In {I.file_name(owner)}", icon="FILE")
            if not obj.visible_get():
                layout.label(text="Hidden, so it is not exported", icon="HIDE_ON")
        for problem in I.problems(obj, scene, check_file=False):
            wrapped(layout, problem, "DOT")


class Card(Properties):
    bl_context = "object"
    bl_parent_id = "XPLANE_PT_object"
    object_types = ("MESH",)

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type in cls.object_types


# The checkboxes of the Clickable card, by the heading they go under and their own text
_CHECKBOXES = {
    "autodetect_datarefs": ("From Animation", "Datarefs"),
    "autodetect_settings_opt_in": ("From Animation", "Direction And Values"),
    "detent_dataref_range": ("Detent Dataref", "Own Range"),
}


def _detent_ranges_layout(layout, manip) -> None:
    target = "object:xplane.manip.axis_detent_ranges"
    col = layout.column(align=True)
    col.label(text="Detents")
    height = "Length" if manip.type == C.MANIP_DRAG_AXIS_DETENT else "Height"
    for i, detent in enumerate(manip.axis_detent_ranges):
        row = col.row(align=True)
        row.prop(detent, "start")
        row.prop(detent, "end")
        row.prop(detent, "height", text=height)
        remove_button(row, target, i)
    add_button(col, target, "Add Detent")


class XPLANE_PT_click(Card, bpy.types.Panel):
    bl_label = "Clickable"
    bl_order = 1

    def draw_header(self, context):
        self.layout.prop(context.object.xplane.manip, "enabled", text="")

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "CLICK")

    def draw(self, context):
        layout = self.layout
        manip = context.object.xplane.manip
        if not manip.enabled:
            wrapped(layout, "Not clickable. Pick what it is to make it clickable in the cockpit:")
            layout.menu(XPLANE_MT_control_kind.bl_idname, text="Make Clickable As...", icon="RESTRICT_SELECT_OFF")
            return
        kind = I.control_kind(manip)
        named(layout, "Acts As").menu(XPLANE_MT_control_kind.bl_idname, text=kind.label)
        wrapped(layout.column(), kind.help, "INFO")
        col = layout.column()
        heading = None
        for field in I.manip_fields(manip):
            if field.kind in ("command", "dataref"):
                text_with_search(col, manip, field.prop, field.label, field.kind, f"object:xplane.manip.{field.prop}")
            elif field.prop in _CHECKBOXES:
                under, text = _CHECKBOXES[field.prop]
                # Checkboxes in a row share one heading
                col.column(heading="" if under == heading else under).prop(manip, field.prop, text=text)
                heading = under
                continue
            else:
                col.prop(manip, field.prop, text=field.label)
        if I.has_detent_ranges(manip):
            _detent_ranges_layout(col, manip)
        col.separator()
        col.prop(manip, "cursor", text="Cursor")
        if manip.type != C.MANIP_NOOP:
            col.prop(manip, "tooltip", text="Tooltip")


class XPLANE_PT_motion(Card, bpy.types.Panel):
    bl_label = "Moves"
    bl_order = 2
    object_types = ALL_TYPES

    def draw(self, context):
        motion_layout(self.layout, context, context.object, context.object)


class XPLANE_PT_visibility(Card, bpy.types.Panel):
    bl_label = "Shows / Hides"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}
    object_types = ALL_TYPES

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "VISIBILITY")

    def draw(self, context):
        visibility_layout(self.layout, context.object)


class XPLANE_PT_glow(Card, bpy.types.Panel):
    bl_label = "Glow"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.prop(context.object.xplane, "lightLevel", text="")

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "GLOW")

    def draw(self, context):
        glow_layout(self.layout.column(), context.object.xplane, "object:xplane.lightLevel_dataref")


class XPLANE_PT_attachment(Card, bpy.types.Panel):
    bl_label = "Attachment Point"
    bl_order = 1
    object_types = ("EMPTY",)

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "ATTACHMENT")

    def draw(self, context):
        layout = self.layout
        special = context.object.xplane.special_empty_props
        layout.prop(special, "special_type", text="Is A")
        col = layout.column()
        if special.special_type == C.EMPTY_USAGE_EMITTER_PARTICLE:
            col.prop(special.emitter_props, "name", text="Emitter")
            switched(col, special.emitter_props, "index_enabled", "index", "Array Index")
        elif special.special_type == C.EMPTY_USAGE_MAGNET:
            col.prop(special.magnet_props, "debug_name", text="Name")
            row = named(col, "Holds")
            row.prop(special.magnet_props, "magnet_type_is_xpad", text="Tablet", toggle=True)
            row.prop(special.magnet_props, "magnet_type_is_flashlight", text="Flashlight", toggle=True)
        elif special.special_type == C.EMPTY_USAGE_WHEEL:
            sub = col.column(align=True)
            sub.prop(special.wheel_props, "gear_index", text="Gear")
            sub.prop(special.wheel_props, "wheel_index", text="Wheel")
        else:
            wrapped(col, "An empty only groups and moves its children.", "INFO")


class XPLANE_PT_more(Card, bpy.types.Panel):
    bl_label = "Advanced"
    bl_order = 9
    bl_options = {"DEFAULT_CLOSED"}
    object_types = ALL_TYPES

    def draw(self, context):
        obj = context.object
        x = obj.xplane
        col = self.layout.column()
        if obj.type == "MESH":
            sub = col.column(heading="Glass")
            sub.prop(x, "hud_glass", text="HUD")
            sub.prop(x, "rain_cannot_escape", text="Rain Cannot Escape")
        draw_order_layout(col, x)
        owners = I.files_of(obj, context.scene)
        lods = int(owners[0].xplane.layer.lods) if owners else 0
        if lods:
            col.column(heading="Distances").prop(x, "override_lods", text="Only Some")
            if x.override_lods:
                grid = named(col, "").grid_flow(row_major=True, columns=2, align=True)
                for i, bucket in enumerate(owners[0].xplane.layer.lod[:lods]):
                    grid.prop(x, "lod", index=i, text=f"{bucket.near}-{bucket.far} m", toggle=True)
        col.column(heading="Export").prop(x, "isExportableRoot", text="As Its Own File")
        if obj.type != "EMPTY":
            custom_lines_layout(col, x, "object:xplane")


classes = (
    XPLANE_PT_object,
    XPLANE_PT_click,
    XPLANE_PT_attachment,
    XPLANE_PT_motion,
    XPLANE_PT_visibility,
    XPLANE_PT_glow,
    XPLANE_PT_more,
)
