"""
Settings of Blender materials: how surfaces are drawn, collide and take part in the cockpit.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute, add_props, light_level_props

SURFACES = (
    (SURFACE_TYPE_NONE, "None"),
    (SURFACE_TYPE_WATER, "Water"),
    (SURFACE_TYPE_CONCRETE, "Concrete"),
    (SURFACE_TYPE_ASPHALT, "Asphalt"),
    (SURFACE_TYPE_GRASS, "Grass"),
    (SURFACE_TYPE_DIRT, "Dirt"),
    (SURFACE_TYPE_GRAVEL, "Gravel"),
    (SURFACE_TYPE_LAKEBED, "Lakebed"),
    (SURFACE_TYPE_SNOW, "Snow"),
    (SURFACE_TYPE_SHOULDER, "Shoulder"),
    (SURFACE_TYPE_BLASTPAD, "Blastpad"),
    (SURFACE_TYPE_SMOOTH, "Smooth"),
)


class XPlaneMaterialSettings(bpy.types.PropertyGroup):
    """bpy.types.Material.xplane"""

    draw: bpy.props.BoolProperty(
        name="Draw Objects With This Material",
        description="Draw the surface. Off: it is not drawn but can still be clicked, for invisible click zones",
        default=True,
    )
    # The name is from X-Plane 10, when it replaced an older on/off setting
    blend_v1000: bpy.props.EnumProperty(
        name="Blend",
        description="How the day texture's alpha is drawn",
        default=BLEND_ON,
        items=[
            (BLEND_OFF, "Alpha Cutoff", "Alpha below Cut Off Below is not drawn, the rest is opaque"),
            (BLEND_ON, "Alpha Blend", "The alpha blends with what is behind"),
            (BLEND_SHADOW, "Shadow", "Drawn blended, but its shadow is cut at Cut Off Below"),
        ],
    )
    blendRatio: bpy.props.FloatProperty(
        name="Alpha Cutoff Ratio",
        description="Alpha below this is not drawn, alpha above it is opaque",
        default=0.5,
        step=0.1,
        precision=2,
        min=0.0,
        max=1.0,
    )
    shadow_local: bpy.props.BoolProperty(
        name="Cast Shadows", description="Objects with this material cast shadows", default=True
    )
    poly_os: bpy.props.IntProperty(
        name="Polygon Offset",
        description="Draws the surface over others at the same place (X-Plane's polygon offset), for decals and labels"
        " that flicker. 0: off",
        default=0,
        step=1,
        min=0,
    )

    surfaceType: bpy.props.EnumProperty(
        name="Surface Type",
        description="The aircraft can stand on the surface, and what kind it is (which sets its bumpiness). None: not solid",
        default=SURFACE_TYPE_NONE,
        items=[(identifier, name, name) for identifier, name in SURFACES],
    )
    deck: bpy.props.BoolProperty(name="Deck", description="The aircraft can also be under the surface, as under a deck", default=False)
    solid_camera: bpy.props.BoolProperty(
        name="Camera Collision",
        description="X-Plane's camera cannot pass through the surface. Cockpit files only",
        default=False,
    )

    cockpit_feature: bpy.props.EnumProperty(
        name="Cockpit Feature",
        description="Show the cockpit's 2D panel or an avionics device on the surface",
        items=[
            (COCKPIT_FEATURE_NONE, "None", "An ordinary surface"),
            (COCKPIT_FEATURE_PANEL, "Panel Texture", "Shows the cockpit's 2D panel, by the object's UVs"),
            (COCKPIT_FEATURE_DEVICE, "Cockpit Device", "Shows one of X-Plane's avionics devices, or a plugin's"),
        ],
    )
    cockpit_region: bpy.props.EnumProperty(
        name="Cockpit Region",
        description="Which region of the cockpit panel texture it shows",
        default="0",
        items=[("0", "None", "None")] + [(str(i),) * 3 for i in range(1, MAX_COCKPIT_REGIONS + 1)],
    )
    cockpit_feature_use_luminance: bpy.props.BoolProperty(
        name="Use Cockpit Panel Luminance", description="Give the screen a real-world brightness"
    )
    cockpit_feature_luminance: bpy.props.IntProperty(
        name="Cockpit Panel Maximum Luminance",
        description="The screen's real-world brightness at its brightest, in nits (cd/m²)",
        min=1,
        max=60000,
        default=1000,
    )
    device_name: bpy.props.EnumProperty(
        name="Cockpit Device Name",
        description="Which of X-Plane's avionics devices the screen shows",
        default=DEVICE_GNS430_1,
        items=[(device, device, device) for device in DEVICES],
    )
    plugin_device: bpy.props.StringProperty(name="Device ID", description="The device ID declared by your plugin")
    device_lighting_channel: bpy.props.IntProperty(
        name="Rheostat Lighting Channel",
        description="The brightness knob of the screen: a 0 based index of X-Plane's lighting channels (rheostats), or -1 for"
        " none (Laminar's G1000 screens use it). Material Glow does not change it",
        default=0,
        min=-1,
    )
    device_auto_adjust: bpy.props.BoolProperty(
        name="Auto-adjust for daytime readability",
        description="The screen brightens by itself to be readable in daylight. Off: it looks washed out in daylight",
        default=True,
    )
    customAttributes: bpy.props.CollectionProperty(
        name="Custom X-Plane Material Attributes",
        description="User defined material attributes for the X-Plane file",
        type=XPlaneCustomAttribute,
    )


add_props(
    XPlaneMaterialSettings,
    {
        **{
            f"device_bus_{i}": bpy.props.BoolProperty(name=f"Bus {i + 1}", description=f"Electrical bus {i + 1} powers the screen")
            for i in range(6)
        },
        **light_level_props("material"),
    },
)
