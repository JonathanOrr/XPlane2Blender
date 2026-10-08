"""
The shapes the X-Plane overlay draws for lights where Blender's own gizmos are turned off.

Blender draws every light with a ground line and, for a spot, a circle whose size is fixed by the angle alone
(10 meters times the sine of half the angle, whatever the cone's length or the light's power). A cockpit has dozens
of lights and an aircraft hundreds, and nothing but hiding them (Overlays > Extras off, which keeps them lighting
the scene) clears the viewport. These shapes replace what that hides: a tick showing where a spot points, and the
cone of the selected lights, kept small.
"""

import math
from typing import List, Optional

import bpy
from mathutils import Vector

from . import draw

# How long the drawn cone of a selected spot is, along its side (meters)
SLANT = 0.4
# Where a spot's tick starts and ends around its ring, in pixels
TICK_FROM, TICK_TO = 8.0, 20.0
EDGES = 4


def direction(obj: bpy.types.Object) -> Optional[Vector]:
    """The way a spot light shines, in world space, or None for a light that shines all around"""
    if obj.type != "LIGHT" or obj.data.type != "SPOT":
        return None
    return (obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))).normalized()


def cone_lines(obj: bpy.types.Object, slant: float = SLANT) -> List[Vector]:
    """
    The cone of a spot light as pairs of points: its edges and the circle it ends in, which is on a sphere of radius
    slant around the light, as Blender draws it (at the widest angle, 180 degrees, it is in the light's own plane)
    """
    shine = direction(obj)
    if shine is None:
        return []
    half = obj.data.spot_size / 2.0
    apex = obj.matrix_world.translation
    center = apex + shine * (slant * math.cos(half))
    radius = slant * math.sin(half)
    ring = draw.circle(center, shine, radius, segments=24)
    side = shine.orthogonal().normalized()
    turn = shine.cross(side)
    edges = []
    for i in range(EDGES):
        angle = 2.0 * math.pi * i / EDGES
        edges += [
            apex,
            center + (side * math.cos(angle) + turn * math.sin(angle)) * radius,
        ]
    return edges + ring


def screen_tick(context, obj: bpy.types.Object, where: Vector) -> List[Vector]:
    """
    A short line outside a spot light's ring, pointing the way it shines, as a pair of points in pixels. where is the
    ring's center. Nothing for a light that shines all around or straight at or away from the viewer
    """
    shine = direction(obj)
    if shine is None:
        return []
    ahead = draw.screen_point(context, obj.matrix_world.translation + shine)
    if ahead is None:
        return []
    along = Vector((ahead.x - where.x, ahead.y - where.y))
    if along.length < 1e-3:
        return []
    along.normalize()
    return [
        Vector((where.x + along.x * TICK_FROM, where.y + along.y * TICK_FROM, 0.0)),
        Vector((where.x + along.x * TICK_TO, where.y + along.y * TICK_TO, 0.0)),
    ]
