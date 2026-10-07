"""
How an animated object moves, read from its keyframes: whether it turns or slides, around or along which axis, how
far at each keyframe, and the dataref value there. The motion overlay and the lever handle draw from this.
Nothing is changed, the keyframes are only evaluated.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import bpy
from mathutils import Euler, Quaternion, Vector

from io_xplane2blender import xplane_helpers
from io_xplane2blender import xplane_inspector as I

TURN, SLIDE = "TURN", "SLIDE"
_MIN_ANGLE = 1e-3  # radians
_MIN_DISTANCE = 1e-6


def interpolate(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Linear interpolation along (xs, ys) like X-Plane's key tables, clamped at the ends. xs may run either way, or there and back"""
    if len(xs) == 1:
        return ys[0]
    lowest = min(range(len(xs)), key=lambda i: xs[i])
    highest = max(range(len(xs)), key=lambda i: xs[i])
    if x <= xs[lowest]:
        return ys[lowest]
    if x >= xs[highest]:
        return ys[highest]
    for i in range(1, len(xs)):
        a, b = xs[i - 1], xs[i]
        if min(a, b) <= x <= max(a, b):
            return (
                ys[i - 1]
                if a == b
                else ys[i - 1] + (ys[i] - ys[i - 1]) * (x - a) / (b - a)
            )
    return ys[-1]


@dataclass
class Motion:
    kind: str  # TURN or SLIDE
    dataref: str
    frames: List[float]
    values: List[float]
    # How far each keyframe is from the first: an angle (radians) around axis, or a distance (world units) along it
    travel: List[float]
    # World space: the point turned around, or where the slide starts; the turning axis, or the slide direction
    origin: Vector
    axis: Vector
    # The travel at the scene's current frame
    now: float

    def frame_at(self, travel: float) -> float:
        return interpolate(travel, self.travel, self.frames)

    def value_at_frame(self, frame: float) -> float:
        return interpolate(frame, self.frames, self.values)

    def value_at(self, travel: float) -> float:
        return self.value_at_frame(self.frame_at(travel))

    @property
    def low(self) -> float:
        return min(self.travel)

    @property
    def high(self) -> float:
        return max(self.travel)


def _keyed(obj: bpy.types.Object) -> Dict[Tuple[str, int], bpy.types.FCurve]:
    return {
        (fc.data_path, fc.array_index): fc
        for fc in xplane_helpers.get_action_fcurves(obj)
    }


def _channel(obj, curves, path: str, frame: float) -> List[float]:
    values = list(getattr(obj, path))
    for i in range(len(values)):
        curve = curves.get((path, i))
        if curve is not None:
            values[i] = curve.evaluate(frame)
    return values


def pose_at(
    obj: bpy.types.Object, frame: float, curves=None
) -> Tuple[Vector, Quaternion]:
    """The object's location and rotation (relative to its parent) at a frame, from its keyframes"""
    curves = _keyed(obj) if curves is None else curves
    location = Vector(_channel(obj, curves, "location", frame))
    mode = obj.rotation_mode
    if mode == "QUATERNION":
        rotation = Quaternion(
            _channel(obj, curves, "rotation_quaternion", frame)
        ).normalized()
    elif mode == "AXIS_ANGLE":
        angle, *axis = _channel(obj, curves, "rotation_axis_angle", frame)
        rotation = (
            Quaternion(Vector(axis), angle) if Vector(axis).length > 0 else Quaternion()
        )
    else:
        rotation = Euler(
            _channel(obj, curves, "rotation_euler", frame), mode
        ).to_quaternion()
    return location, rotation


def _turn(a: Quaternion, b: Quaternion) -> Tuple[Vector, float]:
    """The axis and angle (0 to pi) turning from rotation a to rotation b, in the parent's space"""
    axis, angle = (b @ a.inverted()).to_axis_angle()
    if angle > math.pi:
        axis, angle = -axis, 2 * math.pi - angle
    return axis, angle


def motion_keys(
    obj: bpy.types.Object,
) -> Optional[Tuple[str, List[float], List[float]]]:
    """(dataref, frames, values) of the object's first moving dataref with two keyframes or more"""
    for index, dataref in I.motion_datarefs(obj):
        keys = sorted(I.dataref_keys(obj, index))
        if len(keys) >= 2:
            return dataref.path, [f for f, _ in keys], [v for _, v in keys]
    return None


def motion_of(
    obj: Optional[bpy.types.Object], frame_now: Optional[float] = None
) -> Optional[Motion]:
    """How the object moves through its animation, or None if it is not animated by a dataref"""
    if obj is None or obj.type == "ARMATURE":
        return None
    found = motion_keys(obj)
    if found is None:
        return None
    dataref, frames, values = found
    try:
        to_world = obj.matrix_world @ obj.matrix_basis.inverted()
    except ValueError:  # A scale of 0
        return None
    curves = _keyed(obj)
    poses = [pose_at(obj, f, curves) for f in frames]
    frame_now = bpy.context.scene.frame_current if frame_now is None else frame_now
    segments = [_turn(poses[i - 1][1], poses[i][1]) for i in range(1, len(poses))]
    main_axis, _ = max(segments, key=lambda s: s[1])

    if sum(angle for _, angle in segments) > _MIN_ANGLE:
        travel = [0.0]
        for axis, angle in segments:
            travel.append(travel[-1] + (angle if axis.dot(main_axis) >= 0 else -angle))
        origin = obj.matrix_world.translation.copy()
        world_axis = (to_world.to_3x3() @ main_axis).normalized()
        return Motion(
            TURN,
            dataref,
            frames,
            values,
            travel,
            origin,
            world_axis,
            interpolate(frame_now, frames, travel),
        )

    start = poses[0][0]
    farthest = max(
        (p[0] for p in poses), key=lambda location: (location - start).length
    )
    direction = farthest - start
    if direction.length < _MIN_DISTANCE:
        return None
    direction.normalize()
    scale = (to_world.to_3x3() @ direction).length
    travel = [(p[0] - start).dot(direction) * scale for p in poses]
    world_axis = (to_world.to_3x3() @ direction).normalized()
    return Motion(
        SLIDE,
        dataref,
        frames,
        values,
        travel,
        to_world @ start,
        world_axis,
        interpolate(frame_now, frames, travel),
    )
