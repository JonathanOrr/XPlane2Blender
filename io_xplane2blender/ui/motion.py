"""
Moves and Shows / Hides: datarefs that animate an object, or a bone of an armature (Bone tab).
"""

import bpy

from io_xplane2blender import xplane_anim_presets
from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I

from .common import Properties, compact_row, custom_lines_layout, wrapped
from .ops_object import (
    XPLANE_OT_add_dataref,
    XPLANE_OT_go_to_frame,
    XPLANE_OT_key_pose,
    XPLANE_OT_remove_dataref,
)
from .search import search_button


def _op(layout, idname: str, target: str, text: str = "", icon: str = "NONE"):
    op = layout.operator(idname, text=text, icon=icon)
    op.target = target
    return op


def motion_layout(layout, context, owner, id_data, bone=None) -> None:
    """The datarefs that move owner (an object, or a bone of the armature data id_data)"""
    target = "bone" if bone else "object"
    motion = I.motion_datarefs(owner)
    if bone is None:
        presets = layout.row(align=True)
        presets.operator(xplane_anim_presets.XPLANE_OT_anim_push_button.bl_idname, text="Button")
        presets.operator(xplane_anim_presets.XPLANE_OT_anim_switch.bl_idname, text="Switch")
        presets.operator(xplane_anim_presets.XPLANE_OT_anim_range.bl_idname, text="Knob / Lever")
        if not motion:
            wrapped(layout, "Not animated. Use a preset above, or key it by hand:")
    elif not motion:
        wrapped(layout, "Not animated. Pose the bone in Pose Mode and key it against a dataref:")
    for index, dataref in motion:
        box = layout.box()
        row = box.row(align=True)
        row.prop(dataref, "path", text="")
        search_button(row, "dataref", f"{target}:xplane.datarefs[{index}].path")
        _op(row, XPLANE_OT_remove_dataref.bl_idname, target, icon="X").index = index
        keys = I.dataref_keys(id_data, index, bone)
        if keys:
            flow = box.grid_flow(row_major=True, columns=4, align=True)
            for frame, value in keys:
                current = int(round(frame)) == context.scene.frame_current
                flow.operator(XPLANE_OT_go_to_frame.bl_idname, text=f"{value:g}", depress=current).frame = frame
        row = box.row(align=True)
        row.prop(dataref, "value", text="At")
        _op(row, XPLANE_OT_key_pose.bl_idname, target, "Key Pose", "KEY_HLT").index = index
        box.prop(dataref, "loop", text="Repeats Every")
    op = _op(layout, XPLANE_OT_add_dataref.bl_idname, target, "Add Dataref" if motion else "Key By Hand", "ADD")
    op.anim_type = C.ANIM_TYPE_TRANSFORM


def visibility_layout(layout, owner, bone=None) -> None:
    """The datarefs that show or hide owner"""
    target = "bone" if bone else "object"
    rules = I.visibility_datarefs(owner)
    if not rules:
        wrapped(layout, "Always shown. Add a rule to show or hide it with a dataref:")
    for index, dataref in rules:
        box = layout.box()
        row = compact_row(box)
        row.prop_enum(dataref, "anim_type", C.ANIM_TYPE_SHOW, text="Show")
        row.prop_enum(dataref, "anim_type", C.ANIM_TYPE_HIDE, text="Hide")
        row.label(text="when")
        _op(row, XPLANE_OT_remove_dataref.bl_idname, target, icon="X").index = index
        row = box.row(align=True)
        row.prop(dataref, "path", text="")
        search_button(row, "dataref", f"{target}:xplane.datarefs[{index}].path")
        row = compact_row(box)
        row.prop(dataref, "show_hide_v1", text="is from")
        row.prop(dataref, "show_hide_v2", text="to")
    row = layout.row(align=True)
    _op(row, XPLANE_OT_add_dataref.bl_idname, target, "Show When", "HIDE_OFF").anim_type = C.ANIM_TYPE_SHOW
    _op(row, XPLANE_OT_add_dataref.bl_idname, target, "Hide When", "HIDE_ON").anim_type = C.ANIM_TYPE_HIDE


def draw_order_layout(layout, settings) -> None:
    layout.prop(settings, "override_weight", text="Draw Order")
    if settings.override_weight:
        layout.prop(settings, "weight", text="Order")


class _BoneTab(Properties):
    bl_context = "bone"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return obj is not None and obj.type == "ARMATURE" and getattr(context, "bone", None) is not None


class XPLANE_PT_bone(_BoneTab, bpy.types.Panel):
    bl_label = "X-Plane"

    def draw(self, context):
        moves = [d.path for _, d in I.motion_datarefs(context.bone)]
        rules = [d.path for _, d in I.visibility_datarefs(context.bone)]
        if moves:
            wrapped(self.layout, "Moves with " + ", ".join(moves))
        if rules:
            wrapped(self.layout, "Shows / Hides with " + ", ".join(rules))
        if not moves and not rules:
            wrapped(self.layout, "Not animated")


class XPLANE_PT_bone_moves(_BoneTab, bpy.types.Panel):
    bl_label = "Moves"
    bl_parent_id = "XPLANE_PT_bone"
    bl_order = 2

    def draw(self, context):
        motion_layout(self.layout, context, context.bone, context.object.data, context.bone)


class XPLANE_PT_bone_visibility(_BoneTab, bpy.types.Panel):
    bl_label = "Shows / Hides"
    bl_parent_id = "XPLANE_PT_bone"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        visibility_layout(self.layout, context.bone, context.bone)


class XPLANE_PT_bone_more(_BoneTab, bpy.types.Panel):
    bl_label = "Advanced"
    bl_parent_id = "XPLANE_PT_bone"
    bl_order = 9
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        col = self.layout.column()
        draw_order_layout(col, context.bone.xplane)
        custom_lines_layout(col, context.bone.xplane, "bone:xplane")


classes = (XPLANE_PT_bone, XPLANE_PT_bone_moves, XPLANE_PT_bone_visibility, XPLANE_PT_bone_more)
