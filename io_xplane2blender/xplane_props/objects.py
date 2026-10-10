"""
Settings of Blender objects and armature bones: animation, clicking, light levels and special empties.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute, XPlaneDataref, add_props, light_level_props
from .file import XPlaneLayer
from .manipulator import XPlaneManipulatorSettings


class XPlaneEmitter(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Emitter Name", description="The emitter's name in the particle system file (.pss)")
    index: bpy.props.IntProperty(name="Emitter Index", description="Which emitter of the array this is", min=0)
    index_enabled: bpy.props.BoolProperty(
        name="Emitter Index Enabled", description="The emitter is one of an array of them, with an index", default=False
    )


class XPlaneMagnet(bpy.types.PropertyGroup):
    debug_name: bpy.props.StringProperty(name="Debug Name", description="A name for it in X-Plane's debug output")
    magnet_type_is_xpad: bpy.props.BoolProperty(name="xpad", description="A mount for X-Plane's VR tablet")
    magnet_type_is_flashlight: bpy.props.BoolProperty(
        name="flashlight", description="A mount for X-Plane's VR flashlight"
    )


class XPlaneWheel(bpy.types.PropertyGroup):
    gear_index: bpy.props.IntProperty(
        name="Gear Index", description="Which landing gear of the aircraft, as numbered in Plane Maker", min=0, default=0
    )
    wheel_index: bpy.props.IntProperty(name="Wheel Index", description="Which wheel of that gear", min=0, default=0)


class XPlaneEmpty(bpy.types.PropertyGroup):
    emitter_props: bpy.props.PointerProperty(
        name="Emitter Settings", description="Settings for emitter, if special type is an Emitter", type=XPlaneEmitter
    )
    magnet_props: bpy.props.PointerProperty(
        name="Magnet Settings", description="Settings for magnet, if special type is Magnet", type=XPlaneMagnet
    )
    wheel_props: bpy.props.PointerProperty(
        name="Wheel Settings", description="Settings for the wheel", type=XPlaneWheel
    )
    special_type: bpy.props.EnumProperty(
        name="Empty Special Type",
        description="What X-Plane uses the empty for",
        items=[
            (EMPTY_USAGE_NONE, "None", "Nothing: the empty only holds or moves other objects", 0),
            (EMPTY_USAGE_EMITTER_PARTICLE, "Particle Emitter", "A particle emitter", 1),
            (EMPTY_USAGE_WHEEL, "Wheel", "A wheel", 2),
            (EMPTY_USAGE_MAGNET, "Magnet", "A mounting point on a yoke where a VR tablet can be attached", 3),
        ],
    )


def _weight_props() -> dict:
    return {
        "override_weight": bpy.props.BoolProperty(
            name="Override Weight",
            description="Choose where the object is written in the OBJ: heavier objects are written, and drawn, later",
            default=False,
        ),
        "weight": bpy.props.IntProperty(
            name="Weight",
            description="Heavier is written later. Meshes are usually 0 to 8999, lines 9000 to 9999 and lights 10000 and up",
            default=0,
            min=0,
        ),
    }


def _animation_props() -> dict:
    return {
        "datarefs": bpy.props.CollectionProperty(
            name="X-Plane Datarefs", description="X-Plane Datarefs", type=XPlaneDataref
        ),
        "customAttributes": bpy.props.CollectionProperty(
            name="Custom X-Plane Attributes", description="User defined attributes for the Object", type=XPlaneCustomAttribute
        ),
        "customAnimAttributes": bpy.props.CollectionProperty(
            name="Custom X-Plane Animation Attributes",
            description="User defined attributes for animation of the Object",
            type=XPlaneCustomAttribute,
        ),
    }


class XPlaneObjectSettings(bpy.types.PropertyGroup):
    """bpy.types.Object.xplane"""

    hud_glass: bpy.props.BoolProperty(
        name="HUD Glass", description="The object is the glass of a head-up display (HUD)", default=False
    )
    rain_cannot_escape: bpy.props.BoolProperty(
        name="Rain Cannot Escape", description="Rain does not run from this object onto the parts around it (TRIS_break)", default=False
    )
    override_lods: bpy.props.BoolProperty(
        name="Override LODs",
        description="Choose the levels of detail of this object and its children, instead of their parent's",
        default=False,
    )
    lod: bpy.props.BoolVectorProperty(
        name="Levels Of Detail",
        description="The levels of detail the object is drawn in. None ticked: all of them",
        default=(False, False, False, False),
        size=MAX_LODS - 1,
    )
    # Only used when the object is an empty
    special_empty_props: bpy.props.PointerProperty(
        name="Special Empty Properties", description="Empty Only Properties", type=XPlaneEmpty
    )
    manip: bpy.props.PointerProperty(
        name="Manipulator", description="X-Plane Manipulator Settings", type=XPlaneManipulatorSettings
    )
    isExportableRoot: bpy.props.BoolProperty(
        name="Root Object",
        description="Export this object and its children as their own OBJ file, from the object's origin",
        default=False,
    )
    layer: bpy.props.PointerProperty(
        name="X-Plane Layer", description="X-Plane OBJ File Settings", type=XPlaneLayer
    )


add_props(XPlaneObjectSettings, {**_animation_props(), **light_level_props("object"), **_weight_props()})


class XPlaneBoneSettings(bpy.types.PropertyGroup):
    """bpy.types.Bone.xplane"""

    datarefs: bpy.props.CollectionProperty(
        name="X-Plane Datarefs", description="X-Plane Datarefs", type=XPlaneDataref
    )


add_props(XPlaneBoneSettings, {**_animation_props(), **_weight_props()})
