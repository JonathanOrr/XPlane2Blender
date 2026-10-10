"""
Scene tab, under X-Plane Export: the settings of the file picked in the list.
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.xplane_props.rain import THERMAL_SOURCES as THERMAL_LABELS

from .common import Properties, custom_lines_layout, compact_row
from .file_decals import decals_layout
from .ops_file import XPLANE_OT_textures_from_materials
from .state import active_file


class _FilePanel(Properties):
    bl_context = "scene"
    bl_parent_id = "XPLANE_PT_export"

    @classmethod
    def poll(cls, context):
        return active_file(context) is not None


_MAP_LABELS = {
    "texture_normal": "Normal",
    "texture_map_normal": "Normal",
    "texture_map_material_gloss": "Metal / Gloss",
    "texture_map_gloss": "Gloss",
}


def _cockpit_panel_layout(layout, layer) -> None:
    box = layout.box()
    box.label(text="Cockpit Panel", icon="WINDOW")
    col = box.column()
    col.prop(layer, "cockpit_panel_mode", text="Panel Texture")
    if layer.cockpit_panel_mode != C.PANEL_COCKPIT_REGION:
        return
    col.prop(layer, "cockpit_regions", text="Regions")
    for i, region in enumerate(layer.cockpit_region[: int(layer.cockpit_regions)]):
        sub = col.box().column(align=True)
        sub.label(text=f"Region {i + 1}")
        row = compact_row(sub)
        row.prop(region, "left")
        row.prop(region, "top", text="Bottom")
        row = compact_row(sub)
        row.prop(region, "width", text=f"Width 2^ ({2 ** region.width})")
        row.prop(region, "height", text=f"Height 2^ ({2 ** region.height})")


class XPLANE_PT_file(_FilePanel, bpy.types.Panel):
    bl_label = ""
    bl_order = 1

    def draw_header(self, context):
        self.layout.label(text=f"File: {I.file_name(active_file(context))}")

    def draw(self, context):
        layout = self.layout
        layer = active_file(context).xplane.layer
        col = layout.column()
        col.prop(layer, "name", text="Saved As")
        row = compact_row(col)
        row.prop_enum(layer, "export_type", C.EXPORT_TYPE_AIRCRAFT, text="Aircraft Part")
        row.prop_enum(layer, "export_type", C.EXPORT_TYPE_COCKPIT, text="Cockpit")

        box = layout.box()
        box.label(text="Textures", icon="TEXTURE")
        col = box.column(align=True)
        col.prop(layer, "texture", text="Day")
        col.prop(layer, "texture_lit", text="Night")
        box.prop(layer, "normal_maps", text="Normal And Shine")
        col = box.column(align=True)
        for _, prop in C.NORMAL_MAPS_TEXTURES[layer.normal_maps]:
            col.prop(layer, prop, text=_MAP_LABELS[prop])
        box.operator(XPLANE_OT_textures_from_materials.bl_idname, icon="MATERIAL")

        box = layout.box()
        box.label(text="Look", icon="SHADING_TEXTURE")
        col = box.column()
        col.prop(layer, "blend_glass", text="See-Through Glass")
        col.prop(layer, "normal_metalness", text="Metalness In Normal Map")
        row = compact_row(col)
        row.prop(layer, "specular_override", text="")
        sub = row.row()
        sub.active = layer.specular_override
        sub.prop(layer, "specular", text="Specular (whole file)")
        row = compact_row(col)
        row.prop(layer, "luminance_override", text="")
        sub = row.row()
        sub.active = layer.luminance_override
        sub.prop(layer, "luminance", text="Max Glow (nits)")

        if layer.export_type == C.EXPORT_TYPE_COCKPIT:
            _cockpit_panel_layout(layout, layer)

        box = layout.box()
        box.label(text="Distances (Levels Of Detail)", icon="CON_DISTLIMIT")
        box.prop(layer, "lods", text="Levels")
        for i, lod in enumerate(layer.lod[: int(layer.lods)]):
            row = compact_row(box)
            row.label(text=f"{i + 1}")
            row.prop(lod, "near")
            row.prop(lod, "far")


class XPLANE_PT_file_rain(_FilePanel, bpy.types.Panel):
    bl_label = "Rain, Defrost And Wipers"
    bl_order = 2
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        owner = active_file(context)
        rain = owner.xplane.layer.rain
        layout.prop(rain, "rain_scale")

        box = layout.box()
        box.label(text="Defrost (Thermal)", icon="FREEZE")
        box.prop(rain, "thermal_texture", text="Texture")
        for i, label in enumerate(THERMAL_LABELS, start=1):
            source = getattr(rain, f"thermal_source_{i}")
            col = box.column(align=True)
            col.prop(rain, f"thermal_source_{i}_enabled", text=label)
            if getattr(rain, f"thermal_source_{i}_enabled"):
                col.prop(source, "defrost_time", text="Seconds")
                col.prop(source, "dataref_on_off", text="On/Off Dataref")

        box = layout.box()
        box.label(text="Wipers", icon="MOD_WAVE")
        box.prop(rain, "wiper_texture", text="Gradient Texture")
        box.prop(rain, "wiper_ext_glass_object", text="Outside Glass")
        for i in range(1, 5):
            col = box.column(align=True)
            col.prop(rain, f"wiper_{i}_enabled", text=f"Wiper {i}")
            if not getattr(rain, f"wiper_{i}_enabled"):
                # Wipers are numbered from the first: the export stops at the first one turned off
                break
            wiper = getattr(rain, f"wiper_{i}")
            col.prop(wiper, "object_name", text="Blade Object")
            col.prop(wiper, "dataref", text="Dataref")
            row = compact_row(col)
            row.prop(wiper, "start", text="From")
            row.prop(wiper, "end", text="To")
            col.prop(wiper, "nominal_width", text="Blade Width")

        scene = context.scene
        row = compact_row(box, align=False)
        row.prop(scene.xplane, "wiper_bake_start")
        row.label(text=f"To Frame {scene.xplane.wiper_bake_start + 254}")
        op = box.operator("xplane.bake_wiper_gradient_texture", text=f"Bake For {I.file_name(owner)}")
        op.start = scene.xplane.wiper_bake_start
        op.file = owner.name


class XPLANE_PT_file_decals(_FilePanel, bpy.types.Panel):
    bl_label = "Detail Textures"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        decals_layout(self.layout, active_file(context).xplane.layer)


class XPLANE_PT_file_more(_FilePanel, bpy.types.Panel):
    bl_label = "Advanced"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layer = active_file(context).xplane.layer
        col = self.layout.column()
        col.prop(layer, "particle_system_file", text="Particle Systems (.pss)")
        col.prop(layer, "slungLoadWeight", text="Slung Load Weight (lb)")
        col.prop(layer, "debug", text="Debug Info In This OBJ")
        custom_lines_layout(col, layer, "file:xplane.layer", animation=False, reset=False)


classes = (
    XPLANE_PT_file,
    XPLANE_PT_file_rain,
    XPLANE_PT_file_decals,
    XPLANE_PT_file_more,
)
