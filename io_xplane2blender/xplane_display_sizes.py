"""
How big empties and light cones are drawn in the viewport. Only the viewport: nothing here is exported.

An imported aircraft has thousands of empties (one for each animated part) and hundreds of lights. Blender draws an
empty at a fixed size and a spot light's cone as a long line, so a cockpit of knobs a few centimeters wide ends up
under meter-wide axes and a web of lines that also catch the clicks meant for the part below. Each empty is drawn here
at a fraction of the largest part hanging on it, and a spot light's cone only as long as its reach.
"""

from typing import Dict, Iterable, Optional

import bpy

from .xplane_constants import (
    EMPTY_USAGE_NONE,
    LIGHT_CUSTOM,
    LIGHT_NON_EXPORTING,
    LIGHT_SPILL_CUSTOM,
)

# Of the largest part hanging on an empty, and how small and how large an empty is drawn (in meters)
FRACTION = 0.25
MIN_SIZE = 0.003
MAX_SIZE = 0.06
# An empty with nothing visible on it, such as one that only holds a light
BARE_SIZE = 0.02
# How long a spot light's cone is drawn when the light has no reach of its own (a glow, an exterior light)
CONE_LENGTH = 0.15
MIN_CONE = 0.02


def part_sizes(meshes: Iterable[bpy.types.Object]) -> Dict[bpy.types.Object, float]:
    """The size of the largest mesh below each object, for every object that has one below it"""
    sizes: Dict[bpy.types.Object, float] = {}
    for mesh in meshes:
        size = max(mesh.dimensions)
        parent = mesh.parent
        # Everything above a parent already has at least the size of what the parent has
        while parent is not None and sizes.get(parent, 0.0) < size:
            sizes[parent] = size
            parent = parent.parent
    return sizes


def fit_empty_sizes(
    empties: Iterable[bpy.types.Object],
    sizes: Dict[bpy.types.Object, float],
    unit: float = 1.0,
    bare: Optional[float] = BARE_SIZE,
) -> int:
    """
    Draws the empties at a fraction of the largest part hanging on them, never larger than they are now. unit is the
    size of a meter in the scene. An empty with no part on it is drawn at bare, or left alone when that is None.
    Wheels, tablet mounts and emitters keep their size: they are meant to be seen. Returns how many were changed
    """
    changed = 0
    for empty in empties:
        if (
            empty.type != "EMPTY"
            or empty.xplane.special_empty_props.special_type != EMPTY_USAGE_NONE
        ):
            continue
        part = sizes.get(empty)
        if part is not None:
            wanted = min(max(part * FRACTION, MIN_SIZE * unit), MAX_SIZE * unit)
        elif bare is not None:
            wanted = bare * unit
        else:
            continue
        if empty.empty_display_size - wanted > 1e-6:
            empty.empty_display_size = wanted
            changed += 1
    return changed


# Marks a light whose custom distance is the one this module set, so it can be undone when the light is turned on
TIDIED = "xplane_short_cone"


def fit_cone(
    light: bpy.types.Light,
    reach: Optional[float] = None,
    lit: bool = False,
    unit: float = 1.0,
) -> bool:
    """
    Blender draws a spot light's cone as far as its custom distance, and as far as it lights without one, which is
    tens of meters. A light with a reach gets that as its distance, lit or not: it is how far it lights. Without
    one a light that is off gets CONE_LENGTH, and a light that is lit gets Blender's own distance back, so it lights
    as it should. A distance somebody chose is left alone. Returns whether the light was changed
    """
    if light.type != "SPOT" or not hasattr(light, "use_custom_distance"):
        return False
    ours = bool(light.get(TIDIED))
    if light.use_custom_distance and not ours:
        return False
    if lit and not reach:
        if not ours:
            return False
        light.use_custom_distance = False
        del light[TIDIED]
        return True
    wanted = max(reach if reach else CONE_LENGTH * unit, MIN_CONE * unit)
    if light.use_custom_distance and abs(light.cutoff_distance - wanted) < 1e-6:
        return False
    light.use_custom_distance = True
    light.cutoff_distance = wanted
    light[TIDIED] = True
    return True


def is_lit(light: bpy.types.Light) -> bool:
    """Whether a light lights the scene, which is when it has power. A glow sprite's power is its alpha"""
    return light.energy > 0.0 and light.xplane.type != LIGHT_CUSTOM


def tidy_lights(lights: Iterable[bpy.types.Object], unit: float = 1.0) -> int:
    """fit_cone for the lights of these objects (a light shared by several objects is done once)"""
    done = set()
    changed = 0
    for obj in lights:
        if (
            obj.type != "LIGHT"
            or obj.data in done
            or obj.data.xplane.type == LIGHT_NON_EXPORTING
        ):
            continue
        done.add(obj.data)
        x = obj.data.xplane
        reach = x.size if x.type == LIGHT_SPILL_CUSTOM else None
        changed += fit_cone(obj.data, reach, is_lit(obj.data), unit)
    return changed
