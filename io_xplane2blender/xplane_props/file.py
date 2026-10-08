"""
Settings of an exported OBJ file. A file is a collection (or a root object) with these settings.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneCustomAttribute, add_props
from .decals import decal_props
from .rain import XPlaneRainSettings


class XPlaneCockpitRegion(bpy.types.PropertyGroup):
    # BAD NAME ALERT: Should have been called "bottom", see #416
    top: bpy.props.IntProperty(
        name="Bottom", description="Bottom of cockpit region", default=0, min=0, max=2048
    )
    left: bpy.props.IntProperty(name="Left", description="Left of cockpit region", default=0, min=0, max=2048)
    width: bpy.props.IntProperty(
        name="Width", description="Width of cockpit region in powers of 2", default=1, min=1, max=11
    )
    height: bpy.props.IntProperty(
        name="Height", description="Height of cockpit region in powers of 2", default=1, min=1, max=11
    )


class XPlaneLOD(bpy.types.PropertyGroup):
    near: bpy.props.IntProperty(name="Near", description="Near distance (inclusive) in meters", default=0, min=0)
    far: bpy.props.IntProperty(name="Far", description="Far distance (exclusive) in meters", default=0, min=0)

    def __str__(self) -> str:
        return f"({self.near}, {self.far})"


def _texture(name: str, description: str):
    return bpy.props.StringProperty(subtype="FILE_PATH", name=name, description=description)


class XPlaneLayer(bpy.types.PropertyGroup):
    """Settings of one OBJ file"""

    # The lists of cockpit regions and LODs always have room for the most there can be,
    # so a number in a drop down is all it takes to use more
    def update_cockpit_regions(self, context) -> None:
        while len(self.cockpit_region) < MAX_COCKPIT_REGIONS:
            self.cockpit_region.add()

    def update_lods(self, context) -> None:
        # MAX_LODS also counts "None"
        while len(self.lod) < MAX_LODS - 1:
            self.lod.add()

    name: bpy.props.StringProperty(
        name="Name", description="This name will be used as a filename hint for OBJ file(s)"
    )
    # Blender saves the position in this list. Scenery types were 2 and 3; files using them are
    # converted when opened
    export_type: bpy.props.EnumProperty(
        name="Type",
        description="What kind of thing are you going to export?",
        default=EXPORT_TYPE_AIRCRAFT,
        items=[
            (EXPORT_TYPE_AIRCRAFT, "Aircraft (Part)", "Aircraft (Part)"),
            (EXPORT_TYPE_COCKPIT, "Cockpit", "Cockpit"),
        ],
    )
    debug: bpy.props.BoolProperty(
        name="Debug This OBJ",
        description="If this and the scene's Debug are checked, debug information for this OBJ will be written to"
        " the export log and the OBJ",
        default=True,
    )

    texture: _texture("Texture", "Texture to use for objects on this layer")
    texture_lit: _texture("Night Texture", "Night Texture to use for objects on this layer")
    texture_normal: _texture("Normal/Specular Texture", "Normal/Specular Texture to use for objects on this layer")
    texture_map_normal: _texture("Normal Texture", "XY normal texture to use for objects on this layer")
    texture_map_material_gloss: _texture(
        "Material/Gloss Texture", "Material/Gloss texture to use for objects on this layer"
    )
    texture_map_gloss: _texture("Gloss Texture", "Gloss texture to use for objects on this layer")
    normal_metalness: bpy.props.BoolProperty(
        name="Normal Metalness",
        description="The normal map's blue channel will be used for base reflectance",
        default=False,
    )
    blend_glass: bpy.props.BoolProperty(
        name="Blend Glass",
        description="The alpha channel of the albedo (day texture) will be used to create translucent rendering",
        default=False,
    )
    luminance_override: bpy.props.BoolProperty(
        name="Override Maximum Luminance", description="Override maximum luminance for LIT texture", default=False
    )
    specular_override: bpy.props.BoolProperty(
        name="Override Specular",
        description="Write this file's GLOBAL_specular, the shininess every part has unless its material says"
        " otherwise, including screens and panels, and the materials' Specular where it differs. Off: each material"
        " writes its own, panels none, and with Metalness In Normal Map the file is fully shiny (1)",
        default=False,
    )
    specular: bpy.props.FloatProperty(
        name="Specular",
        description="GLOBAL_specular: 0 to 1. With Metalness In Normal Map it scales the normal map's shine",
        min=0.0,
        max=1.0,
        default=1.0,
    )
    luminance: bpy.props.IntProperty(
        name="Maximum Luminance",
        description="The overriden maximum luminance value for the LIT texture, in nts",
        min=1,
        max=60000,
        default=1000,
    )

    cockpit_panel_mode: bpy.props.EnumProperty(
        name="Panel Texture Mode",
        description="Panel Texture Mode, affects all Materials using Panel",
        items=[
            (PANEL_COCKPIT, "Default", "Full Panel Texture: Albedo, Lit, and Normal"),
            (
                PANEL_COCKPIT_LIT_ONLY,
                "Emissive Panel Texture Only",
                "Only emissive panel texture will be dynamic. Great for computer displays",
            ),
            (PANEL_COCKPIT_REGION, "Regions", "Uses regions of panel texture"),
        ],
        default=PANEL_COCKPIT,
    )
    # BAD NAME ALERT! regions (plural) is the enum, region (singular) is the collection
    cockpit_regions: bpy.props.EnumProperty(
        name="Cockpit Regions",
        description="Number of Cockpit regions to use",
        default="0",
        items=[("0", "None", "None")] + [(str(i),) * 3 for i in range(1, MAX_COCKPIT_REGIONS + 1)],
        update=update_cockpit_regions,
    )
    cockpit_region: bpy.props.CollectionProperty(
        name="Cockpit Region", type=XPlaneCockpitRegion, description="Cockpit Region"
    )
    # lods (plural) is the enum, lod (singular) is the collection
    lods: bpy.props.EnumProperty(
        name="Levels of Detail",
        description="Levels of detail",
        default="0",
        items=[("0", "None", "None")] + [(str(i),) * 3 for i in range(1, MAX_LODS)],
        update=update_lods,
    )
    lod: bpy.props.CollectionProperty(name="LOD", type=XPlaneLOD, description="Level of detail")

    particle_system_file: bpy.props.StringProperty(
        name="Particle System Definition File",
        description="Relative file path to a .pss that defines particles",
        subtype="FILE_PATH",
    )
    rain: bpy.props.PointerProperty(
        type=XPlaneRainSettings,
        name="X-Plane Rain Settings",
        description="Settings related to rain and thermal properties",
    )
    slungLoadWeight: bpy.props.FloatProperty(
        name="Slung Load Weight",
        description="Weight of the object in pounds, for use in the physics engine if the object is being carried"
        " by a plane or helicopter",
        default=0.0,
        step=1,
        precision=3,
    )
    customAttributes: bpy.props.CollectionProperty(
        name="Custom X-Plane Header Attributes",
        description="User defined header attributes for the X-Plane file",
        type=XPlaneCustomAttribute,
    )


add_props(XPlaneLayer, decal_props())


class XPlaneCollectionSettings(bpy.types.PropertyGroup):
    is_exportable_collection: bpy.props.BoolProperty(
        name="Root Collection",
        description="Activate to export all this collection's children as an .obj file",
        default=False,
    )
    layer: bpy.props.PointerProperty(
        name="X-Plane OBJ File Settings", description="X-Plane OBJ File Settings", type=XPlaneLayer
    )
