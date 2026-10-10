"""
Rain on glass: rain scale, defrost (thermal) sources and wipers.
"""

import bpy

from .common import add_props

THERMAL_SOURCES = (
    "Pilot Front Windshield",
    "Copilot Front Windshield",
    "Pilot Side Window",
    "Copilot Side Window",
)


class XPlaneThermalSourceSettings(bpy.types.PropertyGroup):
    defrost_time: bpy.props.StringProperty(
        name="Defrost Time", description="How many seconds it takes to clear the window, or a dataref that gives it"
    )
    dataref_on_off: bpy.props.StringProperty(
        name="Thermal On/Off Dataref", description="The dataref that switches the window heat on and off"
    )


class XPlaneWiperSettings(bpy.types.PropertyGroup):
    object_name: bpy.props.StringProperty(
        name="Blender Wiper Object",
        description="The wiper blade object, whose sweep the gradient texture is baked from",
    )
    dataref: bpy.props.StringProperty(
        name="Wiper animation dref", description="The dataref that moves the wiper"
    )
    start: bpy.props.FloatProperty(name="Wiper Dataref Start", description="The dataref value where the wiper's sweep starts")
    end: bpy.props.FloatProperty(name="Wiper Dataref End", description="The dataref value where the wiper's sweep ends")
    nominal_width: bpy.props.FloatProperty(
        name="Wiper Thickness",
        description="Width of wiper as the percent of wiper animation arc that is covered by the blade at rest."
        " Start low and increase until it looks right",
        default=0.001,
        min=0.0,
        max=1.0,
        precision=3,
    )


class XPlaneRainSettings(bpy.types.PropertyGroup):
    rain_scale: bpy.props.FloatProperty(
        name="Rain Scale",
        description="Scales the rain drops to suit the resolution of the textures",
        default=1.0,
        min=0.1,
        max=1.0,
    )
    thermal_texture: bpy.props.StringProperty(
        name="Thermal Texture", description="The defrost texture, which marks the area each window heat clears", subtype="FILE_PATH"
    )
    wiper_ext_glass_object: bpy.props.StringProperty(
        name="Exterior Glass Object",
        description="The outside glass the wipers sweep (such as the windshield), for the baker",
    )
    wiper_texture: bpy.props.StringProperty(
        name="Wiper Gradient Texture",
        description="The wiper gradient texture, which Bake For makes",
        subtype="FILE_PATH",
    )


def _numbered_props() -> dict:
    props = {}
    for i, where in enumerate(THERMAL_SOURCES, start=1):
        props[f"thermal_source_{i}"] = bpy.props.PointerProperty(
            type=XPlaneThermalSourceSettings,
            name=f"{where} Thermal Source",
            description=f"Thermal Source for the {where.lower()}",
        )
        props[f"thermal_source_{i}_enabled"] = bpy.props.BoolProperty(
            name=f"Enable {where} Thermal Source", description=f"The {where.lower()} is heated against frost"
        )
    for i in range(1, 5):
        props[f"wiper_{i}"] = bpy.props.PointerProperty(
            type=XPlaneWiperSettings, name=f"Wiper {i}", description="Wiper parameters"
        )
        props[f"wiper_{i}_enabled"] = bpy.props.BoolProperty(
            name=f"Enable Wiper {i}", description="Export this wiper. The wipers are numbered from the first"
        )
    return props


add_props(XPlaneRainSettings, _numbered_props())
