"""
The X-Plane pie menu, Shift+Q in the 3D View's Object Mode (change it in Preferences > Keymap > Object Mode):
make clickable, animate, add, key the pose, move to a file, check, export, and the X-Plane overlays.
"""

import bpy

from io_xplane2blender import xplane_anim_presets as presets
from io_xplane2blender import xplane_inspector as I

from .settings import view_settings

_keymaps = []


class XPLANE_MT_animate(bpy.types.Menu):
    bl_idname = "XPLANE_MT_animate"
    bl_label = "Animate As"

    def draw(self, context):
        layout = self.layout
        layout.operator(presets.XPLANE_OT_anim_push_button.bl_idname, text="Push Button")
        layout.operator(presets.XPLANE_OT_anim_switch.bl_idname, text="Switch")
        layout.operator(presets.XPLANE_OT_anim_range.bl_idname, text="Knob / Lever")


class XPLANE_OT_check_in_viewport(bpy.types.Operator):
    """Check the export files for what is not filled in yet and outline it in red in the viewport"""

    bl_idname = "xplane.check_in_viewport"
    bl_label = "Check"
    bl_options = {"REGISTER"}

    def execute(self, context):
        bpy.ops.xplane.check()
        count = len(context.window_manager.xplane_panels.check_items)
        s = view_settings(context)
        if s is not None:
            s.show_unfinished = True
        self.report({"INFO"}, f"{count} thing(s) to finish" if count else "Nothing unfinished")
        return {"FINISHED"}


class XPLANE_MT_pie(bpy.types.Menu):
    bl_idname = "XPLANE_MT_pie"
    bl_label = "X-Plane"

    def draw(self, context):
        # Pie order: left, right, bottom, top, top left, top right, bottom left, bottom right
        pie = self.layout.menu_pie()
        pie.menu("XPLANE_MT_control_kind", text="Make Clickable As", icon="RESTRICT_SELECT_OFF")
        pie.menu(XPLANE_MT_animate.bl_idname, icon="ANIM")
        pie.operator("scene.export_to_relative_dir", text="Export", icon="EXPORT")
        s = view_settings(context)
        if s is not None:
            box = pie.box().column(align=True)
            box.label(text="Show", icon="OVERLAY")
            row = box.row(align=True)
            row.prop(s, "show_click_zones", toggle=True)
            row.prop(s, "show_motion", toggle=True)
            row = box.row(align=True)
            row.prop(s, "show_lever", toggle=True)
            row.prop(s, "show_lights", toggle=True)
        else:
            pie.separator()
        pie.menu("XPLANE_MT_add", text="Add", icon="ADD")
        obj = context.object
        if obj is not None and I.motion_datarefs(obj):
            pie.operator("xplane.key_pose", text="Key This Pose", icon="KEY_HLT")
        else:
            pie.separator()
        pie.menu("XPLANE_MT_move_to_file", text="Move To File", icon="FILE")
        pie.operator(XPLANE_OT_check_in_viewport.bl_idname, icon="CHECKMARK")


classes = (XPLANE_MT_animate, XPLANE_OT_check_in_viewport, XPLANE_MT_pie)


def register_keymap():
    keyconfig = bpy.context.window_manager.keyconfigs.addon
    if keyconfig is None:  # Background mode
        return
    keymap = keyconfig.keymaps.new(name="Object Mode", space_type="EMPTY")
    item = keymap.keymap_items.new("wm.call_menu_pie", "Q", "PRESS", shift=True)
    item.properties.name = XPLANE_MT_pie.bl_idname
    _keymaps.append((keymap, item))


def unregister_keymap():
    for keymap, item in _keymaps:
        keymap.keymap_items.remove(item)
    _keymaps.clear()
