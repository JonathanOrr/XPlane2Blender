"""
The X-Plane Copy tool in the 3D View's toolbar (Object Mode): set up one button, light or attachment, make it
active, then click every other one to give it the same X-Plane settings. The tool settings choose which settings
are copied. Each click is one undo step, and the clicked objects are added to the selection to show what was done.
"""

from typing import Optional

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_inspector as I

from .draw import screen_point

WHAT = (
    (
        "CLICK",
        "Click",
        "What clicking does: kind of control, commands, datarefs, tooltip",
    ),
    ("GLOW", "Glow", "Light level: brightness following a dataref"),
    (
        "VISIBILITY",
        "Shows / Hides",
        "Show and hide animation, added to what the object has",
    ),
    ("LIGHT", "Light", "X-Plane light settings"),
    ("ATTACHMENT", "Attachment", "Wheel, tablet mount or particle emitter settings"),
)
# How near (in pixels) a click must be to a light or empty, which have no surface to hit
PICK_RADIUS = 20


def picked(context, x: float, y: float) -> Optional[bpy.types.Object]:
    """The object under the mouse: the surface hit, or the nearest light or empty"""
    from bpy_extras import view3d_utils

    region, view = context.region, context.region_data
    origin = view3d_utils.region_2d_to_origin_3d(region, view, (x, y))
    direction = view3d_utils.region_2d_to_vector_3d(region, view, (x, y))
    depsgraph = context.evaluated_depsgraph_get()
    hit, *_, obj, _ = context.scene.ray_cast(depsgraph, origin, direction)
    if hit and obj is not None:
        return bpy.data.objects.get(obj.name)
    best, best_distance = None, PICK_RADIUS
    for candidate in context.visible_objects:
        if candidate.type not in ("LIGHT", "EMPTY"):
            continue
        where = screen_point(context, candidate.matrix_world.translation)
        if where is not None and (where - Vector((x, y))).length < best_distance:
            best, best_distance = candidate, (where - Vector((x, y))).length
    return best


def copy_to(source: bpy.types.Object, target: bpy.types.Object, what) -> int:
    """Copies the chosen kinds of settings, returns how many the target could take"""
    return sum(1 for kind in what if I.copy_settings(kind, source, target))


class XPLANE_OT_copy_tool_click(bpy.types.Operator):
    """Give the clicked object the active object's X-Plane settings"""

    bl_idname = "xplane.copy_tool_click"
    bl_label = "Copy X-Plane Settings"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    what: bpy.props.EnumProperty(
        name="Copy", items=WHAT, options={"ENUM_FLAG"}, default={"CLICK"}
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.object is not None

    def invoke(self, context, event):
        source = context.object
        target = picked(context, event.mouse_region_x, event.mouse_region_y)
        if target is None or target == source:
            return {"CANCELLED"}
        copied = copy_to(source, target, self.what)
        if not copied:
            self.report({"WARNING"}, f"{target.name} cannot take those settings")
            return {"CANCELLED"}
        target.select_set(True)
        self.report({"INFO"}, f"{target.name} now has {source.name}'s settings")
        return {"FINISHED"}


class XPLANE_WT_copy(bpy.types.WorkSpaceTool):
    bl_space_type = "VIEW_3D"
    bl_context_mode = "OBJECT"
    bl_idname = "xplane.copy_tool"
    bl_label = "X-Plane Copy"
    bl_description = (
        "Click objects to give them the active object's X-Plane settings,"
        " to set up rows of buttons, lights or attachments alike"
    )
    bl_icon = "brush.paint_texture.clone"
    bl_keymap = (
        (
            XPLANE_OT_copy_tool_click.bl_idname,
            {"type": "LEFTMOUSE", "value": "PRESS"},
            None,
        ),
    )

    @staticmethod
    def draw_settings(context, layout, tool):
        props = tool.operator_properties(XPLANE_OT_copy_tool_click.bl_idname)
        source = context.object
        layout.label(
            text=(
                f"From: {source.name}"
                if source
                else "Make the object to copy from active"
            ),
            icon="COPYDOWN",
        )
        layout.prop(props, "what", expand=True)


classes = (XPLANE_OT_copy_tool_click,)


def register_tool():
    bpy.utils.register_tool(
        XPLANE_WT_copy, after={"builtin.transform"}, separator=True, group=False
    )


def unregister_tool():
    bpy.utils.unregister_tool(XPLANE_WT_copy)
