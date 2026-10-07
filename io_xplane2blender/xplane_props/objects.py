"""
Settings of Blender objects and armature bones: animation, clicking, light levels and special empties.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute, XPlaneDataref, add_props, light_level_props
from .file import XPlaneLayer
from .manipulator import XPlaneManipulatorSettings


class XPlaneEmitter(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Emitter Name", description="The name of the emitter, coming from the .pss file")
    index: bpy.props.IntProperty(name="Emitter Index", description="The index in the emitter's array", min=0)
    index_enabled: bpy.props.BoolProperty(
        name="Emitter Index Enabled", description="Enables the emitter array index", default=False
    )


class XPlaneMagnet(bpy.types.PropertyGroup):
    debug_name: bpy.props.StringProperty(name="Debug Name", description="Human readable name for debugging purposes")
    magnet_type_is_xpad: bpy.props.BoolProperty(name="xpad", description="Sets the type to include 'xpad'")
    magnet_type_is_flashlight: bpy.props.BoolProperty(
        name="flashlight", description="Sets the type to include 'flashlight'"
    )


class XPlaneWheel(bpy.types.PropertyGroup):
    gear_index: bpy.props.IntProperty(name="Gear Index", min=0, default=0)
    wheel_index: bpy.props.IntProperty(name="Wheel Index", min=0, default=0)


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
        description="Type XPlane2Blender item this is",
        items=[
            (EMPTY_USAGE_NONE, "None", "Empty has no special use", 0),
            (EMPTY_USAGE_EMITTER_PARTICLE, "Particle Emitter", "A particle emitter", 1),
            (EMPTY_USAGE_WHEEL, "Wheel", "A wheel", 2),
            (EMPTY_USAGE_MAGNET, "Magnet", "A mounting point on a yoke where a VR tablet can be attached", 3),
        ],
    )


def _weight_props() -> dict:
    return {
        "override_weight": bpy.props.BoolProperty(
            name="Override Weight",
            description="If checked you can override the internal weight of the object. Heavier objects will be"
            " written later in OBJ",
            default=False,
        ),
        "weight": bpy.props.IntProperty(
            name="Weight",
            description="Usual weights are: Meshes 0-8999, Lines 9000 - 9999, Lights > = 10000",
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
        name="HUD Glass", description="Object is the glass of a HUD display", default=False
    )
    rain_cannot_escape: bpy.props.BoolProperty(
        name="Rain Cannot Escape", description="Rain cannot escape from the object", default=False
    )
    override_lods: bpy.props.BoolProperty(
        name="Override LODs",
        description="Overrides any parent's LOD buckets for this object and its children",
        default=False,
    )
    lod: bpy.props.BoolVectorProperty(
        name="Levels Of Detail",
        description="Define in wich LODs this object will be used. If none is checked it will be used in all",
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
        description="Activate to export this object and all its children into it's own .obj file",
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
