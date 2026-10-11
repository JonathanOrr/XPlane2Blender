"""
Delta transforms (Object > Transform > Delta Transform) in animations. Blender adds the delta location to the location,
and turns by the delta rotation after the rotation, in the parent's space. Keying the deltas instead of the location
keeps the keys relative: the part can be moved anywhere afterwards and its animation goes with it.

X-Plane has one chain of moves and turns per animation, so an object's delta rotation goes where it fits:
- STATIC, the same at every key: a fixed turn before the animation, with the keyed locations turned to match
- KEYED while the rotation is not: it is the animated rotation, and the rotation after it is baked into the mesh
- BOTH keyed: one rotation made of the two, exact at the keys
"""

import dataclasses
from typing import Dict, Optional, Union

import bpy
from mathutils import Euler, Matrix, Quaternion

from io_xplane2blender import xplane_helpers

NONE, STATIC, KEYED, BOTH = "NONE", "STATIC", "KEYED", "BOTH"

Rotation = Union[Euler, Quaternion, tuple]


def delta_rotation(obj: bpy.types.Object) -> Optional[Union[Euler, Quaternion]]:
    """A copy of the object's delta rotation in its rotation mode, or None when it does not turn"""
    mode = obj.rotation_mode
    if mode == "AXIS_ANGLE":
        return None  # Blender has no delta rotation for axis and angle
    if mode == "QUATERNION":
        q = obj.delta_rotation_quaternion
        return None if q.magnitude == 0 or abs(q.normalized().w) == 1 else q.copy()
    e = obj.delta_rotation_euler
    return Euler(e, mode) if any(e) else None


def as_quaternion(rotation: Optional[Rotation], mode: str) -> Quaternion:
    if rotation is None:
        return Quaternion()
    if mode == "QUATERNION":
        return Quaternion(rotation).normalized()
    if mode == "AXIS_ANGLE":
        angle, *axis = rotation
        return Quaternion(axis, angle) if any(axis) else Quaternion()
    return Euler(rotation, mode).to_quaternion()


def _all_same(rotations) -> bool:
    """Compared by component: mathutils is single precision. q and -q are the same rotation"""
    first = rotations[0]
    return all(
        max(abs(a - b) for a, b in zip(q if q.dot(first) >= 0 else -q, first)) < 1e-6 for q in rotations
    )


def settle(frames: Dict[int, "LocRotPerFrame"]) -> None:  # noqa: F821
    """Puts one object's delta rotation where X-Plane can do it (see above), in its keyframe infos"""
    infos = list(frames.values())
    if all(i.delta is None for i in infos):
        return
    mode = infos[0].rotation_mode
    deltas = [as_quaternion(i.delta, mode) for i in infos]
    if _all_same(deltas):
        back = deltas[0].inverted()
        for frame, info in frames.items():
            frames[frame] = dataclasses.replace(info, location=back @ info.location, delta_case=STATIC)
    elif _all_same([as_quaternion(i.rotation, mode) for i in infos]):
        unturned = Quaternion() if mode == "QUATERNION" else Euler((0, 0, 0), mode)
        for frame, info in frames.items():
            turn = info.delta if info.delta is not None else unturned
            frames[frame] = dataclasses.replace(info, rotation=turn, delta_case=KEYED)
    else:
        for (frame, info), delta in zip(frames.items(), deltas):
            both = delta @ as_quaternion(info.rotation, mode)
            frames[frame] = dataclasses.replace(info, rotation_mode="QUATERNION", rotation=both, delta_case=BOTH)


def basis_for_animation(obj: bpy.types.Object, case: str) -> Matrix:
    """The object's matrix_basis without a STATIC delta rotation, which X-Plane does before the animation"""
    turn = delta_rotation(obj) if case == STATIC else None
    if turn is None:
        return obj.matrix_basis
    return as_quaternion(turn, obj.rotation_mode).inverted().to_matrix().to_4x4() @ obj.matrix_basis


def rotation_after_animation(obj: bpy.types.Object, case: str) -> Optional[Matrix]:
    """The rotation that follows a KEYED delta rotation, baked into the mesh"""
    if case != KEYED:
        return None
    rotation = xplane_helpers.get_rotation_from_rotatable(obj)
    return as_quaternion(rotation, obj.rotation_mode).to_matrix().to_4x4()
