"""
The X-Plane settings saved in .blend files, as `xplane` on scenes, collections, objects, bones,
materials and lights.

Blender saves the number of the chosen item of a drop down, not its name, so items of an
EnumProperty are never reordered or removed without giving the rest their old numbers. Removed
settings stay in old files as raw values, which the updater can still read with `.get()`.
"""

import bpy

from .common import XPlaneAxisDetentRange, XPlaneCustomAttribute, XPlaneDataref
from .file import XPlaneCockpitRegion, XPlaneCollectionSettings, XPlaneLayer, XPlaneLOD
from .light import LIGHT_TYPE_ITEMS, XPlaneLightSettings
from .manipulator import MANIP_TYPE_ITEMS, XPlaneManipulatorSettings
from .material import XPlaneMaterialSettings
from .objects import (
    XPlaneBoneSettings,
    XPlaneEmitter,
    XPlaneEmpty,
    XPlaneMagnet,
    XPlaneObjectSettings,
    XPlaneWheel,
)
from .rain import XPlaneRainSettings, XPlaneThermalSourceSettings, XPlaneWiperSettings
from .scene import XPlaneSceneSettings
from .version import XPlane2BlenderVersion

# In the order they must be registered: a group after the groups it points to
_classes = (
    XPlane2BlenderVersion,
    XPlaneAxisDetentRange,
    XPlaneCustomAttribute,
    XPlaneDataref,
    XPlaneEmitter,
    XPlaneMagnet,
    XPlaneWheel,
    XPlaneEmpty,
    XPlaneManipulatorSettings,
    XPlaneCockpitRegion,
    XPlaneLOD,
    XPlaneThermalSourceSettings,
    XPlaneWiperSettings,
    XPlaneRainSettings,
    XPlaneLayer,
    XPlaneCollectionSettings,
    XPlaneObjectSettings,
    XPlaneBoneSettings,
    XPlaneMaterialSettings,
    XPlaneLightSettings,
    XPlaneSceneSettings,
)

_owners = (
    (bpy.types.Collection, XPlaneCollectionSettings, "Collection"),
    (bpy.types.Scene, XPlaneSceneSettings, "Scene"),
    (bpy.types.Object, XPlaneObjectSettings, "Object"),
    (bpy.types.Bone, XPlaneBoneSettings, "Bone"),
    (bpy.types.Material, XPlaneMaterialSettings, "Material"),
    (bpy.types.Light, XPlaneLightSettings, "Light"),
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    for owner, settings, name in _owners:
        owner.xplane = bpy.props.PointerProperty(
            type=settings, name=f"X-Plane {name} Settings", description=f"X-Plane {name} Settings"
        )


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
