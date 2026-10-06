"""Coordinate and transform helpers: X-Plane (x right, y up, z back) to Blender (x right, y forward, z up)"""

import math
from typing import Sequence, Tuple

import mathutils

# Maps an X-Plane vector to a Blender vector: (x, y, z) -> (x, -z, y)
_C = mathutils.Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
_C_INV = _C.inverted()

_PRINCIPAL_EPSILON = 1e-5


def vec_to_blender(v: Sequence[float]) -> mathutils.Vector:
    return mathutils.Vector((v[0], -v[2], v[1]))


def matrix_to_blender(m_xp: mathutils.Matrix) -> mathutils.Matrix:
    """Express a transform made in X-Plane space in Blender space"""
    return _C @ m_xp @ _C_INV


def rotation_xp(axis: Sequence[float], degrees: float) -> mathutils.Matrix:
    """The rotation of ANIM_rotate: counter-clockwise (right handed) about the axis, in X-Plane space"""
    vec = mathutils.Vector(axis)
    if vec.length == 0 or degrees == 0:
        return mathutils.Matrix.Identity(4)
    return mathutils.Matrix.Rotation(math.radians(degrees), 4, vec.normalized())


def translation_xp(v: Sequence[float]) -> mathutils.Matrix:
    return mathutils.Matrix.Translation(v)


def principal_axis(axis_xp: Sequence[float]) -> Tuple[int, float]:
    """
    If the X-Plane axis is along one Blender axis returns (index, sign), else (-1, 1.0).
    Used to pick Euler rotation channels that are nice to edit
    """
    axis_bl = vec_to_blender(axis_xp)
    if axis_bl.length == 0:
        return -1, 1.0
    axis_bl.normalize()
    for index in range(3):
        if abs(abs(axis_bl[index]) - 1.0) < _PRINCIPAL_EPSILON:
            return index, 1.0 if axis_bl[index] > 0 else -1.0
    return -1, 1.0


def is_identity(m: mathutils.Matrix, eps: float = 1e-7) -> bool:
    return all(
        abs(m[i][j] - (1.0 if i == j else 0.0)) < eps
        for i in range(4)
        for j in range(4)
    )


def has_rotation(m: mathutils.Matrix, eps: float = 1e-7) -> bool:
    return not is_identity(m.to_3x3().to_4x4(), eps)


def has_translation(m: mathutils.Matrix, eps: float = 1e-7) -> bool:
    return m.to_translation().length > eps
