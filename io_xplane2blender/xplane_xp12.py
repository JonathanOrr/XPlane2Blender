"""
This add-on makes X-Plane 12 aircraft and cockpit objects only. Files saved before version 5 are
converted when they are opened: the settings for older X-Plane versions and for scenery are gone,
so what they chose is read from the values Blender still keeps in the file.
"""

from typing import List

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender.xplane_utils.xplane_updater_helpers import delete_property_from_datablock

FILE_TYPES = (C.EXPORT_TYPE_AIRCRAFT, C.EXPORT_TYPE_COCKPIT)

# What the stored numbers of removed drop down items were
_SCENERY_EXPORT_TYPES = {2: "scenery", 3: "instanced scenery"}
_XP9_LIGHT_TYPES = {0: "default", 1: "flashing", 2: "pulsing", 3: "strobe", 4: "traffic"}


def _names(names: List[str]) -> str:
    names = sorted(names)
    return ", ".join(names[:10]) + (f" and {len(names) - 10} more" if len(names) > 10 else "")


def _file_owners():
    yield from bpy.data.collections
    yield from bpy.data.objects


def convert_to_xp12() -> List[str]:
    """
    Converts what older files chose that X-Plane 12 aircraft can't use. Returns what changed, in words.
    Running it again changes nothing.
    """
    changes = []
    for scene in bpy.data.scenes:
        # Without it the original add-on defaults to X-Plane 12 too
        if delete_property_from_datablock(scene.xplane, "version") is not None:
            changes.append(f"Scene '{scene.name}' is now exported for X-Plane 12")

    scenery = []
    for owner in _file_owners():
        layer = owner.xplane.layer
        if layer.get("export_type") in _SCENERY_EXPORT_TYPES:
            scenery.append(owner.name)
            layer.export_type = C.EXPORT_TYPE_AIRCRAFT
    if scenery:
        changes.append(f"Scenery files are now aircraft files: {_names(scenery)}")

    xp9_lights = []
    for light in bpy.data.lights:
        if light.xplane.get("type") in _XP9_LIGHT_TYPES:
            xp9_lights.append(light.name)
            # With no light chosen it is listed as unfinished work and left out of exports
            light.xplane.type = C.LIGHT_AUTOMATIC
            light.xplane.name = ""
    if xp9_lights:
        changes.append(f"X-Plane 9 lights need an X-Plane 12 light picked: {_names(xp9_lights)}")

    draped = [m.name for m in bpy.data.materials if delete_property_from_datablock(m.xplane, "draped")]
    if draped:
        changes.append(f"Draped (scenery) materials are now normal surfaces: {_names(draped)}")
    return changes
