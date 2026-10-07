"""
Viewport overlay: outlines around what can be clicked in X-Plane, colored by what it does, and labels saying
what each click does ("Button: sim/lights/landing_lights_toggle"). Turned on in the viewport's Overlays popover.
Nothing here is saved or exported.
"""

from typing import Dict, List, Tuple

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_inspector as I

GROUP_COLORS: Dict[str, Tuple[float, float, float, float]] = {
    "Runs commands": (1.0, 0.55, 0.1, 0.9),
    "Sets a dataref": (0.2, 0.8, 1.0, 0.9),
    "Dragged": (0.4, 1.0, 0.3, 0.9),
    "Other": (0.7, 0.7, 0.7, 0.9),
}
# The 12 edges of Blender's bound_box corner order
_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))

_handlers = []


def settings(context):
    return context.window_manager.xplane_sidebar


def clickable(context) -> List[bpy.types.Object]:
    return [o for o in context.visible_objects if o.type == "MESH" and o.xplane.manip.enabled]


def label_of(obj: bpy.types.Object) -> str:
    """What clicking does, in a few words"""
    manip = obj.xplane.manip
    kind = I.control_kind(manip)
    for field in I.manip_fields(manip):
        if field.kind in ("command", "dataref"):
            value = getattr(manip, field.prop).strip()
            if value:
                return f"{kind.label}: {value}"
    return kind.label


def zone_lines(obj: bpy.types.Object) -> List[Vector]:
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return [corners[i] for edge in _EDGES for i in edge]


def _shader():
    import gpu

    for name in ("UNIFORM_COLOR", "3D_UNIFORM_COLOR"):
        try:
            return gpu.shader.from_builtin(name)
        except (ValueError, SystemError):
            continue
    return None


def _draw_zones():
    context = bpy.context
    if not settings(context).show_click_zones:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader

    shader = _shader()
    if shader is None:
        return
    by_group: Dict[str, List[Vector]] = {}
    for obj in clickable(context):
        by_group.setdefault(I.control_kind(obj.xplane.manip).group, []).extend(zone_lines(obj))
    gpu.state.blend_set("ALPHA")
    try:
        gpu.state.line_width_set(2.0)
    except Exception:  # noqa: BLE001 - not every GPU backend has wide lines
        pass
    for group, points in by_group.items():
        batch = batch_for_shader(shader, "LINES", {"pos": points})
        shader.bind()
        shader.uniform_float("color", GROUP_COLORS.get(group, GROUP_COLORS["Other"]))
        batch.draw(shader)
    gpu.state.blend_set("NONE")


def _draw_labels():
    context = bpy.context
    mode = settings(context).click_labels
    if mode == "OFF" or context.region is None or context.region_data is None:
        return
    import blf
    from bpy_extras.view3d_utils import location_3d_to_region_2d

    objects = clickable(context)
    if mode == "SELECTED":
        objects = [o for o in objects if o.select_get()]
    font = 0
    scale = context.preferences.system.ui_scale
    try:
        blf.size(font, 12 * scale)
    except TypeError:
        blf.size(font, int(12 * scale), 72)
    blf.enable(font, blf.SHADOW)
    blf.shadow(font, 3, 0.0, 0.0, 0.0, 0.9)
    for obj in objects:
        center = obj.matrix_world @ (sum((Vector(c) for c in obj.bound_box), Vector()) / 8.0)
        where = location_3d_to_region_2d(context.region, context.region_data, center)
        if where is None:
            continue
        color = GROUP_COLORS.get(I.control_kind(obj.xplane.manip).group, GROUP_COLORS["Other"])
        blf.color(font, color[0], color[1], color[2], 1.0)
        blf.position(font, where.x + 6, where.y - 4, 0)
        blf.draw(font, label_of(obj))
    blf.disable(font, blf.SHADOW)


def overlay_popover(self, context):
    layout = self.layout
    s = settings(context)
    layout.label(text="X-Plane")
    row = layout.row(align=True)
    row.prop(s, "show_click_zones", text="Click Zones")
    row.prop(s, "click_labels", text="")


def register():
    _handlers.append(bpy.types.SpaceView3D.draw_handler_add(_draw_zones, (), "WINDOW", "POST_VIEW"))
    _handlers.append(bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), "WINDOW", "POST_PIXEL"))
    bpy.types.VIEW3D_PT_overlay.append(overlay_popover)


def unregister():
    bpy.types.VIEW3D_PT_overlay.remove(overlay_popover)
    for handler in _handlers:
        bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
    _handlers.clear()
