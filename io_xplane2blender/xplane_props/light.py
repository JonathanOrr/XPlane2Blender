"""
Settings of Blender lights: which X-Plane light each one becomes.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute

# Blender saves the number of the chosen item. 0 to 4 were the X-Plane 9 lights, which files
# are converted away from when they are opened
LIGHT_TYPE_ITEMS = [
    (LIGHT_NAMED, "Named", "A lights.txt light with no parameters", 5),
    (LIGHT_CUSTOM, "Custom Billboard", "Custom billboard light", 6),
    (LIGHT_PARAM, "Manual Param", "A lights.txt light with its parameters typed by hand", 7),
    (LIGHT_AUTOMATIC, "Automatic", "Makes named and param lights with params taken from Blender light data", 8),
    (LIGHT_SPILL_CUSTOM, "Custom Spill", "Custom spill light, with automatic parameter detection", 9),
    (LIGHT_NON_EXPORTING, "Non-Exporting", "Light will not be in the OBJ", 10),
]


class XPlaneLightSettings(bpy.types.PropertyGroup):
    """bpy.types.Light.xplane"""

    type: bpy.props.EnumProperty(
        name="Type",
        description="Defines the type of the light in X-Plane",
        default=LIGHT_AUTOMATIC,
        items=LIGHT_TYPE_ITEMS,
    )
    name: bpy.props.StringProperty(name="Name", description="Name from lights.txt, see the summary for more detail")
    params: bpy.props.StringProperty(
        name="Parameters",
        description="The additional parameters vary in number and definition based on the particular parameterized"
        " light selected",
    )
    enable_rgb_override: bpy.props.BoolProperty(
        name="Enable RGB Picker Override",
        description="Used instead of the Blender color picker to input any RGB values. Useful for certain datarefs",
        default=False,
    )
    rgb_override_values: bpy.props.FloatVectorProperty(
        name="RGB Override Values",
        description="The values that will be used instead of the RGB picker",
        default=(0.0, 0.0, 0.0),
        subtype="NONE",
        unit="NONE",
        precision=3,
        size=3,
    )
    param_freq: bpy.props.FloatProperty(
        name="Flash Frequency", description="The number of light flashes per second", min=0.0
    )
    param_intensity_new: bpy.props.FloatProperty(
        name="Intensity",
        description="Total light output in a specific direction, in candela",
        min=0.01,
        max=1000000,
        default=20000,
    )
    param_index: bpy.props.IntProperty(
        name="Dataref Index", description="Index in light's associated array dataref", min=0, max=127
    )
    param_phase: bpy.props.FloatProperty(
        name="Phase Offset",
        description="Phase offset in seconds of light (so it can make flashing lights that don't flash at the same time)",
        min=0.0,
    )
    param_size: bpy.props.FloatProperty(
        name="Light Size",
        description="Spill size uses meters; billboard size uses arbitrary scales - bigger is brighter",
        default=1.0,
        min=LIGHT_PARAM_SIZE_MIN,
        precision=3,
    )
    size: bpy.props.FloatProperty(name="Size", description="Size parameter for Custom Lights", default=1.0)
    dataref: bpy.props.StringProperty(name="Dataref", description="An X-Plane Dataref")
    uv: bpy.props.FloatVectorProperty(
        name="Texture Coordinates",
        description="The texture coordinates in the following order: left,top,right,bottom (fractions from 0 to 1)",
        default=(0.0, 0.0, 1.0, 1.0),
        min=0.0,
        max=1.0,
        precision=3,
        size=4,
    )
    customAttributes: bpy.props.CollectionProperty(
        name="Custom X-Plane Light Attributes",
        description="User defined light attributes for the X-Plane file",
        type=XPlaneCustomAttribute,
    )
