"""
Where the imported keyframes are on the timeline.

Each part is keyed with the key nearest its dataref's default value on frame 1 (motion.apply), so the keys of lower
values are before it, where Blender's playhead cannot go. Once everything is imported, all the keys move by the same
number of frames so the first is on frame 1. The parked pose is then one frame for every part, where the scene opens.
"""

from typing import Iterable

import bpy
import numpy as np

from io_xplane2blender import xplane_helpers


def settle(objects: Iterable[bpy.types.Object], scene: bpy.types.Scene) -> int:
    """Moves the keys of the objects to frame 1 onwards and opens the scene on the parked pose, which it returns"""
    curves = []
    for obj in objects:
        try:
            curves.extend(xplane_helpers.get_action_fcurves(obj))
        except ReferenceError:  # Removed while the parts were joined
            continue
    curves = [c for c in curves if len(c.keyframe_points)]
    if not curves:
        return scene.frame_current
    first = min(c.keyframe_points[0].co[0] for c in curves)
    last = max(c.keyframe_points[-1].co[0] for c in curves)
    shift = max(0, round(1 - first))
    if shift:
        for curve in curves:
            _shift(curve, shift)
    parked = 1 + shift
    scene.frame_end = max(scene.frame_end, int(round(last)) + shift)
    scene.frame_set(parked)
    return parked


def _shift(curve: bpy.types.FCurve, frames: int) -> None:
    points = curve.keyframe_points
    for attribute in ("co", "handle_left", "handle_right"):
        values = np.zeros(len(points) * 2)
        points.foreach_get(attribute, values)
        values[0::2] += frames
        points.foreach_set(attribute, values)
    curve.update()
