"""
Settings of Blender materials: how surfaces are drawn, collide and take part in the cockpit.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute, add_props, light_level_props

DEVICES = (
    DEVICE_GNS430_1,
    DEVICE_GNS430_2,
    DEVICE_GNS530_1,
    DEVICE_GNS530_2,
    DEVICE_CDU739_1,
    DEVICE_CDU739_2,
    DEVICE_G1000_PFD1,
    DEVICE_G1000_MFD,
    DEVICE_G1000_PFD2,
    DEVICE_CDU815_1,
    DEVICE_CDU815_2,
    DEVICE_Primus_PFD_1,
    DEVICE_Primus_PFD_2,
    DEVICE_Primus_MFD_1,
    DEVICE_Primus_MFD_2,
    DEVICE_Primus_MFD_3,
    DEVICE_Primus_RMU_1,
    DEVICE_Primus_RMU_2,
    DEVICE_MCDU_1,
    DEVICE_MCDU_2,
    DEVICE_PLUGIN,
)

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
        description="If turned off, objects with this material won't be drawn",
        default=True,
    )
    # The name is from X-Plane 10, when it replaced an older on/off setting
    blend_v1000: bpy.props.EnumProperty(
        name="Blend",
        description="Controls texture alpha/blending",
        default=BLEND_ON,
        items=[
            (BLEND_OFF, "Alpha Cutoff", "Textures alpha channel will be used to cutoff areas above the Alpha cutoff ratio"),
            (BLEND_ON, "Alpha Blend", "Textures alpha channel will blended"),
            (BLEND_SHADOW, "Shadow", "In shadow mode, shadows are not blended but primary drawing is"),
        ],
    )
    blendRatio: bpy.props.FloatProperty(
        name="Alpha Cutoff Ratio",
        description="Levels in the texture below this level are rendered as fully transparent and levels above this"
        " level are fully opaque",
        default=0.5,
        step=0.1,
        precision=2,
        min=0.0,
        max=1.0,
    )
    shadow_local: bpy.props.BoolProperty(
        name="Cast Shadows", description="If enabled, objects with this material cast shadows", default=True
    )
    poly_os: bpy.props.IntProperty(
        name="Polygon Offset",
        description="Draws the surface on top of the ones under it (X-Plane's polygon offset), for decals and labels that flicker. Leave at 0 for default behaviour",
        default=0,
        step=1,
        min=0,
    )

    surfaceType: bpy.props.EnumProperty(
        name="Surface Type",
        description="Controls the bumpiness of material in X-Plane",
        default=SURFACE_TYPE_NONE,
        items=[(identifier, name, name) for identifier, name in SURFACES],
    )
    deck: bpy.props.BoolProperty(name="Deck", description="Allows the user to fly under the surface", default=False)
    solid_camera: bpy.props.BoolProperty(
        name="Camera Collision",
        description="X-Plane's camera will be prevented from moving through objects with this material. Only allowed"
        " in Cockpit type exports",
        default=False,
    )

    cockpit_feature: bpy.props.EnumProperty(
        name="Cockpit Feature",
        description="What cockpit feature to enable",
        items=[
            (COCKPIT_FEATURE_NONE, "None", "Material uses no advanced cockpit features"),
            (COCKPIT_FEATURE_PANEL, "Panel Texture", "Material uses Panel Texture"),
            (COCKPIT_FEATURE_DEVICE, "Cockpit Device", "Material uses Device Texture"),
        ],
    )
    cockpit_region: bpy.props.EnumProperty(
        name="Cockpit Region",
        description="Cockpit region to use",
        default="0",
        items=[("0", "None", "None")] + [(str(i),) * 3 for i in range(1, MAX_COCKPIT_REGIONS + 1)],
    )
    cockpit_feature_use_luminance: bpy.props.BoolProperty(
        name="Use Cockpit Panel Luminance", description="Use cockpit panel luminance feature"
    )
    cockpit_feature_luminance: bpy.props.IntProperty(
        name="Cockpit Panel Maximum Luminance",
        description="Real world maximum brightness of the panel, in nts",
        min=1,
        max=60000,
        default=1000,
    )
    device_name: bpy.props.EnumProperty(
        name="Cockpit Device Name",
        description="GPS device name",
        default=DEVICE_GNS430_1,
        items=[(device, device, device) for device in DEVICES],
    )
    plugin_device: bpy.props.StringProperty(name="Device ID", description="The device ID declared by your plugin")
    device_lighting_channel: bpy.props.IntProperty(
        name="Rheostat Lighting Channel",
        description="The brightness knob of the screen: a 0 based index of X-Plane's lighting channels (rheostats), or -1 for"
        " none (Laminar's G1000 screens use it). Not affected by 'Light Level'",
        default=0,
        min=-1,
    )
    device_auto_adjust: bpy.props.BoolProperty(
        name="Auto-adjust for daytime readability",
        description="If true, the screen brightens automatically to be readable in the day. Otherwise it is"
        " 'washed out' in daylight",
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
            f"device_bus_{i}": bpy.props.BoolProperty(name=f"Bus {i + 1}", description=f"System bus {i + 1}")
            for i in range(6)
        },
        **light_level_props("material"),
    },
)
