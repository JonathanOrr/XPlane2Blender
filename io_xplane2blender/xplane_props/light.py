"""
Settings of Blender lights: which X-Plane light each one becomes.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute

# Blender saves the number of the chosen item. 0 to 4 were the X-Plane 9 lights, which files
# are converted away from when they are opened
LIGHT_TYPE_ITEMS = [
    (
        LIGHT_AUTOMATIC,
        "Library Light",
        "A light from X-Plane's lights.txt; color, cone and direction come from the Blender light",
        8,
    ),
    (
        LIGHT_SPILL_CUSTOM,
        "Spill",
        "Lights up the surfaces around it (cockpit flood lights, panel lights)",
        9,
    ),
    (
        LIGHT_CUSTOM,
        "Glow Sprite",
        "A halo drawn from part of the texture; it lights nothing",
        6,
    ),
    (LIGHT_NAMED, "Library Light, By Name", "A lights.txt light with no parameters", 5),
    (
        LIGHT_PARAM,
        "Library Light, Manual",
        "A lights.txt light with its parameters set by hand",
        7,
    ),
    (LIGHT_NON_EXPORTING, "Not Exported", "Only for the Blender scene", 10),
]


def _changed(quantity):
    """The settings' update function: the Blender light follows what was changed (see xplane_light_sync)"""

    def update(self, context):
        from io_xplane2blender import xplane_light_sync

        xplane_light_sync.stored_changed(self.id_data, quantity)

    return update


class XPlaneLightSettings(bpy.types.PropertyGroup):
    """bpy.types.Light.xplane"""

    type: bpy.props.EnumProperty(
        name="Type",
        description="Defines the type of the light in X-Plane",
        default=LIGHT_AUTOMATIC,
        items=LIGHT_TYPE_ITEMS,
    )
    name: bpy.props.StringProperty(
        name="Name", description="Name from lights.txt, see the summary for more detail"
    )
    params: bpy.props.StringProperty(
        name="Parameters",
        description="The additional parameters vary in number and definition based on the particular parameterized"
        " light selected",
        update=_changed(None),
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
        name="Flash Frequency",
        description="The number of light flashes per second",
        min=0.0,
    )
    param_intensity_new: bpy.props.FloatProperty(
        name="Intensity",
        description="Total light output in a specific direction, in candela. It is the Blender light's Power while that"
        " is above 0",
        min=0.01,
        max=1000000,
        default=20000,
        update=_changed("intensity"),
    )
    param_index: bpy.props.IntProperty(
        name="Dataref Index",
        description="Index in light's associated array dataref",
        min=0,
        max=127,
    )
    param_phase: bpy.props.FloatProperty(
        name="Phase Offset",
        description="Phase offset in seconds of light (so it can make flashing lights that don't flash at the same time)",
        min=0.0,
    )
    param_size: bpy.props.FloatProperty(
        name="Light Size",
        description="Spill size uses meters, and is how far it reaches (the Blender light's Custom Distance); billboard"
        " size uses arbitrary scales - bigger is brighter",
        default=1.0,
        min=LIGHT_PARAM_SIZE_MIN,
        precision=3,
        update=_changed("reach"),
    )
    size: bpy.props.FloatProperty(
        name="Size",
        description="Size parameter for Custom Lights. For a Spill it is how far it reaches in meters (the Blender"
        " light's Custom Distance)",
        default=1.0,
        update=_changed("reach"),
    )
    spill_dim: bpy.props.FloatProperty(
        name="Dim",
        description="The alpha of a Spill: 1 is full brightness, 0 is off until its dataref brightens it",
        default=1.0,
        min=0.0,
        max=1.0,
        precision=3,
    )
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
