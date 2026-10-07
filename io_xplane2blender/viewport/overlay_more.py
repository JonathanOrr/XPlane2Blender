"""
More viewport overlays:
- Motion: the path the selected animated objects travel from their first to their last keyframe, a tick and the
  dataref value at each keyframe, and the hinge line of turning parts
- Lights: a ring in each X-Plane light's color, the selected ones named (red when no light is chosen yet)
- Unfinished: red outlines around what the last Check listed, the selected ones saying what is missing
"""

from typing import List, Optional

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C

from . import draw
from .motion import TURN, Motion, motion_of

MOTION_COLOR = (1.0, 0.8, 0.2, 0.95)
HINGE_COLOR = (1.0, 0.8, 0.2, 0.45)
PROBLEM_COLOR = (1.0, 0.25, 0.2, 0.95)
MAX_MOTIONS = 64
ARC_STEPS = 32


def short_name(dataref: str) -> str:
    return dataref.rstrip("/").rsplit("/", 1)[-1] or dataref


def hub_and_arm(obj: bpy.types.Object, motion: Motion):
    """For a turning part: the hub on the axis level with the part's middle, and the arm from there to it"""
    v = draw.box_center(obj) - motion.origin
    along = motion.axis * v.dot(motion.axis)
    arm = v - along
    if arm.length < 1e-5:
        size = max(max(obj.dimensions), 0.01) * 0.5
        arm = motion.axis.orthogonal().normalized() * size
    return motion.origin + along, arm


def motion_shape(obj: bpy.types.Object, motion: Motion):
    """(path as pairs of points, the point of each keyframe, the hinge line) of where the part's middle travels"""
    if motion.kind == TURN:
        hub, arm = hub_and_arm(obj, motion)
        steps = [
            motion.low + (motion.high - motion.low) * i / ARC_STEPS
            for i in range(ARC_STEPS + 1)
        ]
        path = draw.strip(
            draw.arc(hub, motion.axis, arm, [t - motion.now for t in steps])
        )
        keys = draw.arc(hub, motion.axis, arm, [t - motion.now for t in motion.travel])
        hinge = [
            hub - motion.axis * arm.length * 0.6,
            hub + motion.axis * arm.length * 0.6,
        ]
        return path, keys, hinge
    base = draw.box_center(obj) - motion.axis * motion.now
    path = [base + motion.axis * motion.low, base + motion.axis * motion.high]
    return path, [base + motion.axis * t for t in motion.travel], []


def _ticks(points: List[Vector], size: float) -> List[Vector]:
    out = []
    for p in points:
        for d in (Vector((size, 0, 0)), Vector((0, size, 0)), Vector((0, 0, size))):
            out += [p - d, p + d]
    return out


def _motions(context):
    found = []
    for obj in context.selected_objects[:MAX_MOTIONS]:
        motion = motion_of(obj)
        if motion is not None:
            found.append((obj, motion))
    return found


def draw_motion(context) -> None:
    points, hinges = [], []
    for obj, motion in _motions(context):
        path, keys, hinge = motion_shape(obj, motion)
        span = (
            (path[0] - path[-1]).length
            if motion.kind != TURN
            else (keys[0] - hinge[0]).length
        )
        points += path + _ticks(keys, max(span * 0.03, 0.002))
        hinges += hinge
    draw.lines(points, MOTION_COLOR)
    draw.lines(hinges, HINGE_COLOR, width=1.0)


def draw_motion_labels(context) -> None:
    text = draw.Text(context, size=11)
    frame = context.scene.frame_current
    for obj, motion in _motions(context):
        _, keys, _ = motion_shape(obj, motion)
        shown = range(len(keys)) if len(keys) <= 6 else (0, len(keys) - 1)
        for i in shown:
            text.at(keys[i], f"{motion.values[i]:g}", MOTION_COLOR)
        if obj == context.object:
            now = motion.value_at_frame(frame)
            text.at(
                draw.box_center(obj),
                f"{short_name(motion.dataref)} = {now:.3g}",
                (1, 1, 1, 1),
                dy=-22,
            )
    text.done()


def light_color(light: bpy.types.Light):
    settings = light.xplane
    rgb = (
        settings.rgb_override_values[:]
        if settings.enable_rgb_override
        else light.color[:]
    )
    return (*(min(max(c, 0.0), 1.0) for c in rgb), 1.0)


def light_name(light: bpy.types.Light) -> Optional[str]:
    """What the light exports as, or None when a library light has no light chosen yet"""
    settings = light.xplane
    if settings.type in (C.LIGHT_AUTOMATIC, C.LIGHT_NAMED, C.LIGHT_PARAM):
        return settings.name.strip() or None
    return {C.LIGHT_CUSTOM: "Glow sprite", C.LIGHT_SPILL_CUSTOM: "Spill"}.get(
        settings.type, ""
    )


def x_plane_lights(context) -> List[bpy.types.Object]:
    return [
        o
        for o in context.visible_objects
        if o.type == "LIGHT" and o.data.xplane.type != C.LIGHT_NON_EXPORTING
    ]


def draw_lights(context) -> None:
    text = draw.Text(context, size=11)
    by_color = {}
    for obj in x_plane_lights(context):
        where = draw.screen_point(context, obj.matrix_world.translation)
        if where is None:
            continue
        name = light_name(obj.data)
        color = light_color(obj.data) if name is not None else PROBLEM_COLOR
        ring = draw.circle(
            Vector((where.x, where.y, 0)), Vector((0, 0, 1)), 6, segments=12
        )
        by_color.setdefault(color, []).extend(ring)
        if obj.select_get():
            text.at(
                obj.matrix_world.translation,
                name if name is not None else "No light chosen",
                color,
                dx=9,
            )
    for color, ring in by_color.items():
        draw.lines(ring, color, width=2.0)
    text.done()


def unfinished_objects(context):
    names = {
        item.object_name: item.text
        for item in context.window_manager.xplane_panels.check_items
    }
    return [(o, names[o.name]) for o in context.visible_objects if o.name in names]


def draw_unfinished(context) -> None:
    points = []
    for obj, _ in unfinished_objects(context):
        points += draw.box_lines(obj)
    draw.lines(points, PROBLEM_COLOR)


def draw_unfinished_labels(context) -> None:
    text = draw.Text(context, size=11)
    for obj, problem in unfinished_objects(context):
        if obj.select_get():
            text.at(draw.box_center(obj), problem, PROBLEM_COLOR)
    text.done()
