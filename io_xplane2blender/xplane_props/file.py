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
        name="Bottom", description="The region's bottom edge on the panel texture, in pixels", default=0, min=0, max=2048
    )
    left: bpy.props.IntProperty(name="Left", description="The region's left edge on the panel texture, in pixels", default=0, min=0, max=2048)
    width: bpy.props.IntProperty(
        name="Width", description="The region's width in pixels, as a power of 2", default=1, min=1, max=11
    )
    height: bpy.props.IntProperty(
        name="Height", description="The region's height in pixels, as a power of 2", default=1, min=1, max=11
    )


class XPlaneLOD(bpy.types.PropertyGroup):
    near: bpy.props.IntProperty(name="Near", description="Drawn from this distance, in meters", default=0, min=0)
    far: bpy.props.IntProperty(name="Far", description="Drawn up to this distance, in meters", default=0, min=0)

    def __str__(self) -> str:
        return f"({self.near}, {self.far})"


def _texture(name: str, description: str):
    return bpy.props.StringProperty(subtype="FILE_PATH", name=name, description=description)


def _get_normal_maps(self) -> int:
    """Files from before the choice existed use the textures they have"""
    stored = self.get("normal_maps")
    if stored is not None:
        return stored
    if self.texture_normal or not (
        self.texture_map_normal or self.texture_map_material_gloss or self.texture_map_gloss
    ):
        return 0
    return 2 if self.texture_map_gloss and not self.texture_map_material_gloss else 1


def _set_normal_maps(self, value: int) -> None:
    self["normal_maps"] = value


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
        name="Name", description="The OBJ's file name, or a path relative to the .blend file"
    )
    # Blender saves the position in this list. Scenery types were 2 and 3; files using them are
    # converted when opened
    export_type: bpy.props.EnumProperty(
        name="Type",
        description="An aircraft part, or the cockpit OBJ",
        default=EXPORT_TYPE_AIRCRAFT,
        items=[
            (EXPORT_TYPE_AIRCRAFT, "Aircraft (Part)", "A part of the aircraft, seen from outside and inside"),
            (EXPORT_TYPE_COCKPIT, "Cockpit", "The cockpit OBJ: clickable parts, panel textures and camera collision"),
        ],
    )
    debug: bpy.props.BoolProperty(
        name="Debug This OBJ",
        description="With the scene's Debug Info on, write debug comments into this OBJ and the export log",
        default=True,
    )

    texture: _texture("Day Texture", "TEXTURE: the color (albedo) texture of every part of the file")
    texture_lit: _texture("Night Texture", "TEXTURE_LIT: the texture that glows at night, drawn over the day texture")
    normal_maps: bpy.props.EnumProperty(
        name="Normal And Shine",
        description="How the file's normal map and shine are textured",
        items=[
            (
                NORMAL_MAPS_ONE,
                "One Texture",
                "TEXTURE_NORMAL: red and green are the normal, alpha the gloss and, with Metalness In Normal Map,"
                " blue the metalness",
                0,
            ),
            (
                NORMAL_MAPS_MATERIAL_GLOSS,
                "Normal + Metal / Gloss Maps",
                "X-Plane 12's separate maps: TEXTURE_MAP normal and TEXTURE_MAP material_gloss, red the metalness"
                " and green the gloss",
                1,
            ),
            (
                NORMAL_MAPS_GLOSS,
                "Normal + Gloss Maps",
                "X-Plane 12's separate maps: TEXTURE_MAP normal and TEXTURE_MAP gloss, red the gloss",
                2,
            ),
        ],
        get=_get_normal_maps,
        set=_set_normal_maps,
    )
    texture_normal: _texture("Normal Texture", "TEXTURE_NORMAL: the normal map, with the gloss in its alpha")
    texture_map_normal: _texture("Normal Map", "TEXTURE_MAP normal: the normal map, in red and green")
    texture_map_material_gloss: _texture(
        "Metal / Gloss Map", "TEXTURE_MAP material_gloss: the metalness in red and the gloss in green"
    )
    texture_map_gloss: _texture("Gloss Map", "TEXTURE_MAP gloss: the gloss, in red")
    normal_metalness: bpy.props.BoolProperty(
        name="Normal Metalness",
        description="The normal map's blue is the metalness (base reflectance)",
        default=False,
    )
    blend_glass: bpy.props.BoolProperty(
        name="Blend Glass",
        description="Draw the file as see-through glass, as clear as the day texture's alpha",
        default=False,
    )
    luminance_override: bpy.props.BoolProperty(
        name="Override Maximum Luminance", description="Set the brightest the night (LIT) texture gets", default=False
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
        description="The brightest the night (LIT) texture gets, in nits (cd/m²)",
        min=1,
        max=60000,
        default=1000,
    )

    cockpit_panel_mode: bpy.props.EnumProperty(
        name="Panel Texture Mode",
        description="What the 2D panel screens of the file show",
        items=[
            (PANEL_COCKPIT, "Default", "The whole panel texture: day, night and normal"),
            (
                PANEL_COCKPIT_LIT_ONLY,
                "Emissive Panel Texture Only",
                "Only the night (emissive) panel texture changes, good for computer screens",
            ),
            (PANEL_COCKPIT_REGION, "Regions", "Parts (regions) of the panel texture"),
        ],
        default=PANEL_COCKPIT,
    )
    # BAD NAME ALERT! regions (plural) is the enum, region (singular) is the collection
    cockpit_regions: bpy.props.EnumProperty(
        name="Cockpit Regions",
        description="How many regions of the panel texture the screens use",
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
        description="How many levels of detail the file has: each draws its objects between two distances",
        default="0",
        items=[("0", "None", "None")] + [(str(i),) * 3 for i in range(1, MAX_LODS)],
        update=update_lods,
    )
    lod: bpy.props.CollectionProperty(name="LOD", type=XPlaneLOD, description="Level of detail")

    particle_system_file: bpy.props.StringProperty(
        name="Particle System Definition File",
        description="The particle system file (.pss) the file's emitters use",
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
        description="OBJ lines typed by hand for the file",
        type=XPlaneCustomAttribute,
    )


add_props(XPlaneLayer, decal_props())


class XPlaneCollectionSettings(bpy.types.PropertyGroup):
    is_exportable_collection: bpy.props.BoolProperty(
        name="Root Collection",
        description="Export everything in this collection as one OBJ file",
        default=False,
    )
    layer: bpy.props.PointerProperty(
        name="X-Plane OBJ File Settings", description="X-Plane OBJ File Settings", type=XPlaneLayer
    )
