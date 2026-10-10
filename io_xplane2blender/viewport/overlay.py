"""
Viewport overlay: outlines around what can be clicked in X-Plane, colored by what it does, an arrow for a typed
drag direction, and labels saying what each click does ("Button: sim/lights/landing_lights_toggle"). Turned on in
the viewport's Overlays popover, which also has the motion, light and unfinished work overlays and the lever handle.
Nothing here is exported.
"""

from typing import Dict, List, Tuple

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.xplane_helpers import vec_x_to_b

from . import draw
from .settings import view_settings

GROUP_COLORS: Dict[str, Tuple[float, float, float, float]] = {
    "Runs commands": (1.0, 0.55, 0.1, 0.9),
    "Sets a dataref": (0.2, 0.8, 1.0, 0.9),
    "Dragged": (0.4, 1.0, 0.3, 0.9),
    "Other": (0.7, 0.7, 0.7, 0.9),
}


def clickable(context) -> List[bpy.types.Object]:
    return [
        o
        for o in context.visible_objects
        if o.type == "MESH" and o.xplane.manip.enabled
    ]


def label_of(obj: bpy.types.Object) -> str:
    """What clicking does, in a few words"""
    manip = obj.xplane.manip
    kind = I.control_kind(manip)
    if manip.type == C.MANIP_DEVICE:
        device = manip.plugin_device if manip.device_name == C.DEVICE_PLUGIN else manip.device_name
        return f"{kind.label}: {device}"
    for field in I.manip_fields(manip):
        if field.kind in ("command", "dataref"):
            value = getattr(manip, field.prop).strip()
            if value:
                return f"{kind.label}: {value}"
    return kind.label


def zone_lines(obj: bpy.types.Object) -> List[Vector]:
    return draw.box_lines(obj)


def drag_arrow(obj: bpy.types.Object) -> List[Vector]:
    """
    For a click zone dragged along a typed direction (drag along without following animation, command axis): an
    arrow from its middle along that direction, as pairs of points. The direction is in the OBJ's coordinates, drawn
    here as if the file's root were the scene's origin
    """
    manip = obj.xplane.manip
    typed = manip.type == C.MANIP_COMMAND_AXIS or (
        manip.type == C.MANIP_DRAG_AXIS and not manip.autodetect_settings_opt_in
    )
    direction = vec_x_to_b((manip.dx, manip.dy, manip.dz)) if typed else Vector()
    if direction.length < 1e-6:
        return []
    start = draw.box_center(obj)
    end = start + direction
    side = direction.orthogonal().normalized() * direction.length * 0.12
    back = end - direction * 0.2
    return [start, end, end, back + side, end, back - side]


def color_of(obj: bpy.types.Object):
    return GROUP_COLORS.get(
        I.control_kind(obj.xplane.manip).group, GROUP_COLORS["Other"]
    )


def draw_zones(context) -> None:
    by_group: Dict[str, List[Vector]] = {}
    for obj in clickable(context):
        by_group.setdefault(I.control_kind(obj.xplane.manip).group, []).extend(
            zone_lines(obj) + drag_arrow(obj)
        )
    for group, points in by_group.items():
        draw.lines(points, GROUP_COLORS.get(group, GROUP_COLORS["Other"]))


def draw_labels(context, mode: str) -> None:
    objects = clickable(context)
    if mode == "SELECTED":
        objects = [o for o in objects if o.select_get()]
    text = draw.Text(context)
    for obj in objects:
        text.at(draw.box_center(obj), label_of(obj), color_of(obj))
    text.done()


def overlay_popover(self, context):
    s = view_settings(context)
    if s is None:
        return
    layout = self.layout
    layout.label(text="X-Plane")
    row = layout.row(align=True)
    row.prop(s, "show_click_zones", text="Click Zones")
    row.prop(s, "click_labels", text="")
    grid = layout.grid_flow(columns=2, even_columns=True, align=True)
    grid.prop(s, "show_motion")
    grid.prop(s, "show_lever")
    grid.prop(s, "show_lights")
    grid.prop(s, "show_unfinished")
