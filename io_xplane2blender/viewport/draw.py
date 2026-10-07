"""
Small drawing helpers for the overlays: colored lines in the 3D view and text on screen. They only run inside
a 3D View's draw callback.
"""

import math
from typing import Iterable, List, Sequence, Tuple

import bpy
from mathutils import Matrix, Vector

Color = Tuple[float, float, float, float]

# The 12 edges of Blender's bound_box corner order
BOX_EDGES = ((0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7))


def box_lines(obj: bpy.types.Object) -> List[Vector]:
    """The object's bounding box in world space, as pairs of points"""
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return [corners[i] for edge in BOX_EDGES for i in edge]


def box_center(obj: bpy.types.Object) -> Vector:
    return obj.matrix_world @ (sum((Vector(c) for c in obj.bound_box), Vector()) / 8.0)


def strip(points: Sequence[Vector]) -> List[Vector]:
    """A polyline as pairs of points, to draw as LINES"""
    return [p for i in range(1, len(points)) for p in (points[i - 1], points[i])]


def circle(center: Vector, normal: Vector, radius: float, segments: int = 24) -> List[Vector]:
    """A closed circle as pairs of points"""
    turn = normal.to_track_quat("Z", "Y").to_matrix()
    ring = [center + turn @ Vector((math.cos(a), math.sin(a), 0)) * radius for a in _angles(segments)]
    return strip(ring + ring[:1])


def _angles(segments: int) -> Iterable[float]:
    return (2 * math.pi * i / segments for i in range(segments))


def arc(center: Vector, axis: Vector, start: Vector, angles: Sequence[float]) -> List[Vector]:
    """Points of start turned around axis (through center) by each angle"""
    return [center + Matrix.Rotation(a, 3, axis) @ start for a in angles]


def _shader():
    import gpu

    for name in ("UNIFORM_COLOR", "3D_UNIFORM_COLOR"):
        try:
            return gpu.shader.from_builtin(name)
        except (ValueError, SystemError):
            continue
    return None


def lines(points: List[Vector], color: Color, width: float = 2.0) -> None:
    """Draws pairs of points in the 3D view, in a POST_VIEW callback"""
    if not points:
        return
    import gpu
    from gpu_extras.batch import batch_for_shader

    shader = _shader()
    if shader is None:
        return
    gpu.state.blend_set("ALPHA")
    try:
        gpu.state.line_width_set(width)
    except Exception:  # noqa: BLE001 - not every GPU backend has wide lines
        pass
    batch = batch_for_shader(shader, "LINES", {"pos": points})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def screen_point(context, point: Vector):
    """Where a world point is in the region, or None behind the view"""
    from bpy_extras.view3d_utils import location_3d_to_region_2d

    if context.region is None or context.region_data is None:
        return None
    return location_3d_to_region_2d(context.region, context.region_data, point)


class Text:
    """Text with a shadow, drawn in a POST_PIXEL callback"""

    def __init__(self, context, size: int = 12):
        import blf

        self.blf = blf
        self.context = context
        scale = context.preferences.system.ui_scale
        try:
            blf.size(0, size * scale)
        except TypeError:
            blf.size(0, int(size * scale), 72)
        blf.enable(0, blf.SHADOW)
        blf.shadow(0, 3, 0.0, 0.0, 0.0, 0.9)

    def at(self, point: Vector, text: str, color: Color, dx: float = 6, dy: float = -4) -> None:
        where = screen_point(self.context, point)
        if where is None:
            return
        self.blf.color(0, color[0], color[1], color[2], 1.0)
        self.blf.position(0, where.x + dx, where.y + dy, 0)
        self.blf.draw(0, text)

    def done(self) -> None:
        self.blf.disable(0, self.blf.SHADOW)
