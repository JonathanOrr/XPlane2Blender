"""
One dataref's animation of one object, kept as plain numbers until it is known which object carries it.

An ANIM block is an object that moves. X-Plane draws a part under a chain of them (a translation, then a rotation, in
any order, each with a dataref), but a Blender object can hold more: the exporter reads one dataref's keys off the
location and rotation of the object, so a part that is pushed in and turned by the same dataref is one object, and so
is a part turned about three axes. Only different datarefs, or a move after a turn, need an object each. The importer
builds a Motion for every ANIM_trans and ANIM_rotate, joins what one object can show, and keys the result onto the
object that carries the mesh.
"""

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import mathutils
import numpy as np

from . import transforms as T
from .defaults import nearest_key_index
from .obj_parser import AnimOp

EPSILON = 1e-6
AXES = "XYZ"


@dataclass
class Spin:
    """A turn about one axis (Blender space, unit length): the angle in radians at every key"""

    axis: mathutils.Vector
    angles: List[float]


@dataclass
class Motion:
    """What a dataref does to an object: its location and its turns, at the dataref values in `values`"""

    dataref: str
    loop: float
    values: List[float]
    location: Optional[List[mathutils.Vector]] = None
    spins: List[Spin] = field(default_factory=list)


def from_translation(op: AnimOp, offset: mathutils.Vector, scale: float) -> Motion:
    keys = sorted(op.keys, key=lambda k: k[0])
    return Motion(
        op.dataref,
        op.loop,
        [k[0] for k in keys],
        location=[offset + T.vec_to_blender(k[1]) * scale for k in keys],
    )


def from_rotation(op: AnimOp) -> Motion:
    keys = sorted(op.keys, key=lambda k: k[0])
    if mathutils.Vector(op.axis).length:
        axis = T.vec_to_blender(op.axis).normalized()
    else:
        axis = mathutils.Vector((0, 0, 1))
    spin = Spin(axis, [math.radians(k[1][0]) for k in keys])
    return Motion(op.dataref, op.loop, [k[0] for k in keys], spins=[spin])


def euler_order(spins: List[Spin]) -> Optional[str]:
    """
    The rotation mode with which one object turns about these axes, outermost first, or None when it cannot:
    Euler angles turn about the three axes of Blender only, each once. 'XYZ' is the turn about X first (innermost)
    """
    indices = []
    for spin in spins:
        index, _ = T.principal_axis_bl(spin.axis)
        if index < 0 or index in indices:
            return None
        indices.append(index)
    inner_first = list(reversed(indices)) + [i for i in (2, 1, 0) if i not in indices]
    return "".join(AXES[i] for i in inner_first)


def _at(values: List[float], rows: list, wanted: List[float]) -> np.ndarray:
    """Linear interpolation of columns of numbers given at `values`, at the `wanted` values (held beyond the ends)"""
    table = np.array(rows, dtype=float).reshape(len(values), -1)
    return np.stack(
        [np.interp(wanted, values, table[:, c]) for c in range(table.shape[1])], axis=1
    )


def combine(outer: Motion, inner: Motion, shift: mathutils.Vector) -> Optional[Motion]:
    """
    The motion of an object that does `outer` and then, `shift` further along, `inner`. None when no single object
    shows both: their datarefs differ, a turn comes before a move or before a different pivot, or the turns are not
    about the axes of one Euler rotation
    """
    if outer.dataref != inner.dataref or outer.loop != inner.loop:
        return None
    if outer.spins and (inner.location or shift.length > EPSILON or not inner.spins):
        return None
    spins = outer.spins + inner.spins
    if len(spins) > 1 and euler_order(spins) is None:
        return None
    for motion in (outer, inner):
        if len(set(motion.values)) != len(motion.values):
            return None
    values = sorted(set(outer.values) | set(inner.values))
    location = None
    if outer.location or inner.location:
        total = np.zeros((len(values), 3))
        for part, moved in ((outer, False), (inner, True)):
            if part.location:
                total += _at(part.values, [tuple(v) for v in part.location], values)
        total += np.array(shift)
        location = [mathutils.Vector(row) for row in total]
    resampled = []
    for spin, motion in [(s, outer) for s in outer.spins] + [
        (s, inner) for s in inner.spins
    ]:
        angles = _at(motion.values, [[a] for a in spin.angles], values)[:, 0]
        resampled.append(Spin(spin.axis, [float(a) for a in angles]))
    return Motion(outer.dataref, outer.loop, values, location, resampled)


def shifted(
    motion: Motion,
    by: Optional[mathutils.Vector],
    turn: Optional[mathutils.Matrix] = None,
) -> None:
    """Moves the object that does this motion: turns every key of its location, then moves it. A turn alone has no keys"""
    if not motion.location:
        return
    keys = [turn @ v for v in motion.location] if turn is not None else motion.location
    motion.location = [v + by for v in keys] if by is not None else list(keys)


def apply(
    obj, motion: Motion, add_dataref: Callable[[object, str, float], object]
) -> None:
    """Keys the motion onto the object, which gets the dataref. X-Plane interpolates linearly between keys"""
    dataref = add_dataref(obj, motion.dataref, motion.loop)
    # The key nearest the dataref's default value goes on frame 1, so the scene opens in the parked pose
    first = 1 - nearest_key_index(motion.values, motion.dataref)
    mode = _rotation_mode(motion)
    if mode:
        obj.rotation_mode = mode
    for i, value in enumerate(motion.values):
        frame = first + i
        dataref.value = value
        dataref.keyframe_insert(data_path="value", frame=frame)
        if motion.location:
            obj.location = motion.location[i]
            obj.keyframe_insert(data_path="location", frame=frame)
        _set_rotation(obj, motion, i, frame)
    _linear(obj)


def _rotation_mode(motion: Motion) -> str:
    if not motion.spins:
        return ""
    if len(motion.spins) > 1:
        return euler_order(motion.spins)
    index, _ = T.principal_axis_bl(motion.spins[0].axis)
    return "XYZ" if index >= 0 else "AXIS_ANGLE"


def _set_rotation(obj, motion: Motion, i: int, frame: int) -> None:
    if len(motion.spins) == 1 and obj.rotation_mode == "AXIS_ANGLE":
        spin = motion.spins[0]
        obj.rotation_axis_angle = (spin.angles[i], *spin.axis)
        obj.keyframe_insert(data_path="rotation_axis_angle", frame=frame)
        return
    for spin in motion.spins:
        index, sign = T.principal_axis_bl(spin.axis)
        obj.rotation_euler[index] = sign * spin.angles[i]
    for spin in motion.spins:
        index, _ = T.principal_axis_bl(spin.axis)
        obj.keyframe_insert(data_path="rotation_euler", index=index, frame=frame)


def _linear(obj) -> None:
    from io_xplane2blender import xplane_helpers

    try:
        fcurves = xplane_helpers.get_action_fcurves(obj)
    except Exception:
        fcurves = []
    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "LINEAR"
        fcurve.update()
