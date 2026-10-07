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
        name="Defrost Time", description="Defrost time in seconds (Can be a dataref)"
    )
    dataref_on_off: bpy.props.StringProperty(
        name="Thermal On/Off Dataref", description="Dataref that controls source on/off"
    )


class XPlaneWiperSettings(bpy.types.PropertyGroup):
    object_name: bpy.props.StringProperty(
        name="Blender Wiper Object",
        description="Name of wiper object, used in creation of wiper gradient texture",
    )
    dataref: bpy.props.StringProperty(
        name="Wiper animation dref", description="The dataref that controls the motion of the wiper object"
    )
    start: bpy.props.FloatProperty(name="Wiper Dataref Start", description="Start dataref value of Wiper animation")
    end: bpy.props.FloatProperty(name="Wiper Dataref End", description="End dataref value of Wiper animation")
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
        description="Scales the visual output of rain to match texture resolution",
        default=1.0,
        min=0.1,
        max=1.0,
    )
    thermal_texture: bpy.props.StringProperty(
        name="Thermal Texture", description="File path to the thermal texture", subtype="FILE_PATH"
    )
    wiper_ext_glass_object: bpy.props.StringProperty(
        name="Exterior Glass Object",
        description="Name of Object to be used as exterior glass (such as a Windshield) by the baker",
    )
    wiper_texture: bpy.props.StringProperty(
        name="Wiper Gradient Texture",
        description="File path to the wiper gradient texture (click 'Make Wiper Gradient Texture' to make)",
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
        props[f"thermal_source_{i}_enabled"] = bpy.props.BoolProperty(name=f"Enable {where} Thermal Source")
    for i in range(1, 5):
        props[f"wiper_{i}"] = bpy.props.PointerProperty(
            type=XPlaneWiperSettings, name=f"Wiper {i}", description="Wiper parameters"
        )
        props[f"wiper_{i}_enabled"] = bpy.props.BoolProperty(name=f"Enable Wiper {i}")
    return props


add_props(XPlaneRainSettings, _numbered_props())
