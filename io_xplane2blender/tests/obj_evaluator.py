"""
Evaluates an OBJ file the way X-Plane would, for tests: returns where every triangle corner ends up
for chosen dataref values. Comparing two OBJs this way shows whether they look the same,
however differently their ANIM blocks and TRIS runs are arranged.
"""

import math
from typing import Callable, Dict, List, Optional

import numpy as np

from io_xplane2blender.xplane_importer.obj_parser import (
    AnimNode,
    AnimOp,
    ObjFile,
    TrisRun,
    parse_obj,
)


def _rotation(axis, degrees: float) -> np.ndarray:
    axis = np.array(axis, dtype=float)
    length = np.linalg.norm(axis)
    if length == 0 or degrees == 0:
        return np.eye(4)
    x, y, z = axis / length
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    matrix = np.eye(4)
    matrix[:3, :3] = [
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ]
    return matrix


def _interpolate(keys, value: float) -> np.ndarray:
    """Linear between keys, held at the first and last key outside of them"""
    keys = sorted(keys, key=lambda k: k[0])
    if value <= keys[0][0]:
        return np.array(keys[0][1], dtype=float)
    for (v0, a), (v1, b) in zip(keys, keys[1:]):
        if v0 <= value <= v1:
            t = 0.0 if v1 == v0 else (value - v0) / (v1 - v0)
            return np.array(a, dtype=float) * (1 - t) + np.array(b, dtype=float) * t
    return np.array(keys[-1][1], dtype=float)


def _op_matrix(op: AnimOp, value: float) -> np.ndarray:
    if op.kind == "trans":
        matrix = np.eye(4)
        matrix[:3, 3] = (
            _interpolate(op.keys, value) if not op.is_static else op.keys[0][1]
        )
        return matrix
    angle = (
        float(_interpolate(op.keys, value)[0]) if not op.is_static else op.keys[0][1][0]
    )
    return _rotation(op.axis, angle)


def corners(
    obj: ObjFile,
    dataref_values: Optional[Dict[str, float]] = None,
    default: Callable[[str], float] = lambda path: 0.0,
) -> np.ndarray:
    """An (N, 3) array of every drawn triangle corner in X-Plane space, in a stable order"""
    values = dataref_values or {}
    points: List[np.ndarray] = []

    def value_of(dataref: str) -> float:
        return values.get(dataref, default(dataref))

    def visit(node: AnimNode, matrix: np.ndarray) -> None:
        for op in node.ops:
            matrix = matrix @ _op_matrix(
                op, 0.0 if op.is_static else value_of(op.dataref)
            )
        hidden = False
        for vis in node.visibility:
            inside = min(vis.v1, vis.v2) <= value_of(vis.dataref) <= max(vis.v1, vis.v2)
            hidden = hidden or (not inside if vis.kind == "show" else inside)
        if hidden:
            return
        for child in node.children:
            if isinstance(child, AnimNode):
                visit(child, matrix)
            elif isinstance(child, TrisRun):
                indices = obj.indices[child.offset : child.offset + child.count]
                local = np.hstack(
                    [obj.vertices[indices, 0:3], np.ones((len(indices), 1))]
                )
                points.append((local @ matrix.T)[:, :3])

    visit(obj.root, np.eye(4))
    if not points:
        return np.zeros((0, 3))
    stacked = np.vstack(points)
    # Sorted by rounded values so that two files list the same corners in the same order
    rounded = np.round(stacked, 2)
    order = np.lexsort((rounded[:, 2], rounded[:, 1], rounded[:, 0]))
    return stacked[order]


def corners_from_text(
    text: str, dataref_values=None, default=lambda path: 0.0
) -> np.ndarray:
    return corners(parse_obj(text), dataref_values, default)


def max_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    The largest distance from a corner in one set to the nearest corner of the other, both ways.
    Corners are compared as sets, so how two files order their triangles does not matter.
    """
    from mathutils import kdtree

    if len(a) == 0 or len(b) == 0:
        return 0.0 if len(a) == len(b) else float("inf")
    worst = 0.0
    for source, target in ((a, b), (b, a)):
        tree = kdtree.KDTree(len(target))
        for i, point in enumerate(target):
            tree.insert(point.tolist(), i)
        tree.balance()
        for point in source:
            worst = max(worst, tree.find(point.tolist())[2])
    return worst
