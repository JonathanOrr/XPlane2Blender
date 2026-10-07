"""
This fork makes X-Plane 12 aircraft and cockpits only. Files made for older X-Plane versions or for scenery
are converted when they are opened or imported, so they are one click away from an X-Plane 12 export.

The exporter itself still knows the older versions: its code stays close to upstream XPlane2Blender so fixes
can move between the two. Only the settings that pick an older version or scenery are changed here.
"""

import os
from typing import List

import bpy

from io_xplane2blender import xplane_constants

LATEST_VERSION = xplane_constants.VERSION_1220
FILE_TYPES = (xplane_constants.EXPORT_TYPE_AIRCRAFT, xplane_constants.EXPORT_TYPE_COCKPIT)
LEGACY_LIGHT_TYPES = {
    xplane_constants.LIGHT_DEFAULT,
    xplane_constants.LIGHT_FLASHING,
    xplane_constants.LIGHT_PULSING,
    xplane_constants.LIGHT_STROBE,
    xplane_constants.LIGHT_TRAFFIC,
}

# The upstream export tests check the exporter at the X-Plane version saved in each test file
KEEP_OLD_SETTINGS_VARIABLE = "XPLANE2BLENDER_KEEP_OLD_SETTINGS"


def keep_old_settings() -> bool:
    return bool(os.environ.get(KEEP_OLD_SETTINGS_VARIABLE))


def _has_layer_settings():
    yield from bpy.data.collections
    yield from bpy.data.objects


def convert_to_xp12() -> List[str]:
    """
    Changes the settings that target older X-Plane versions or scenery. Returns what changed, in words.
    Running it again changes nothing.
    """
    changes = []
    for scene in bpy.data.scenes:
        if scene.xplane.version != LATEST_VERSION:
            changes.append(f"Scene '{scene.name}': X-Plane version setting changed to 12")
            scene.xplane.version = LATEST_VERSION

    for owner in _has_layer_settings():
        layer = owner.xplane.layer
        if layer.export_type not in FILE_TYPES:
            changes.append(f"'{owner.name}' was a scenery file, it is now an aircraft file")
            layer.export_type = xplane_constants.EXPORT_TYPE_AIRCRAFT

    legacy_lights = [light.name for light in bpy.data.lights if light.xplane.type in LEGACY_LIGHT_TYPES]
    if legacy_lights:
        # There is no faithful X-Plane 12 version of these, so they are pointed out rather than changed
        changes.append(
            f"{len(legacy_lights)} light(s) use the old X-Plane 9 light types and still export as before: "
            + ", ".join(sorted(legacy_lights)[:10])
            + (" ..." if len(legacy_lights) > 10 else "")
        )
    return changes
