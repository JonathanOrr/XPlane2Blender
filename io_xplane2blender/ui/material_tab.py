"""
Material tab: how surfaces with the material are drawn, whether they are a screen, and how solid they are.
Materials are shared, so the panel says how many meshes a change reaches.
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I

from .common import Properties, custom_lines_layout, glow_layout, wrapped

BLEND_LABELS = ((C.BLEND_ON, "Smooth"), (C.BLEND_OFF, "Hard Edge"), (C.BLEND_SHADOW, "Cut Shadow"))
SCREEN_LABELS = (
    (C.COCKPIT_FEATURE_NONE, "None"),
    (C.COCKPIT_FEATURE_PANEL, "2D Panel"),
    (C.COCKPIT_FEATURE_DEVICE, "Avionics"),
)


class _MaterialTab(Properties):
    bl_context = "material"

    @classmethod
    def poll(cls, context):
        obj = context.object
        return context.material is not None and obj is not None and obj.type == "MESH"


def _screen_layout(col, context, m) -> None:
    col.label(text="Screen")
    row = col.row(align=True)
    for value, label in SCREEN_LABELS:
        row.prop_enum(m, "cockpit_feature", value, text=label)
    if m.cockpit_feature == C.COCKPIT_FEATURE_PANEL:
        owners = I.files_of(context.object, context.scene)
        if owners and owners[0].xplane.layer.cockpit_panel_mode == C.PANEL_COCKPIT_REGION:
            col.prop(m, "cockpit_region", text="Panel Region")
        else:
            wrapped(col, "Shows the aircraft's 2D panel, mapped by the UVs.", "INFO")
    elif m.cockpit_feature == C.COCKPIT_FEATURE_DEVICE:
        col.prop(m, "device_name", text="Device")
        if m.device_name == C.DEVICE_PLUGIN:
            col.prop(m, "plugin_device")
        col.label(text="Powered By")
        grid = col.grid_flow(row_major=True, columns=3, align=True)
        for bus in range(6):
            grid.prop(m, f"device_bus_{bus}", toggle=True)
        col.prop(m, "device_lighting_channel", text="Brightness Knob (Channel)")
        col.prop(m, "device_auto_adjust", text="Brighter In Daylight")
    if m.cockpit_feature != C.COCKPIT_FEATURE_NONE:
        row = col.row(align=True)
        row.prop(m, "cockpit_feature_use_luminance", text="")
        sub = row.row()
        sub.active = m.cockpit_feature_use_luminance
        sub.prop(m, "cockpit_feature_luminance", text="Max Brightness (nits)")


class XPLANE_PT_surface(_MaterialTab, bpy.types.Panel):
    bl_label = "X-Plane"

    def draw(self, context):
        layout = self.layout
        material = context.material
        # Each mesh using the material is one user
        users = material.users - (1 if material.use_fake_user else 0)
        if users > 1:
            layout.label(text=f"Shared by {users} meshes: changes apply to all", icon="LINKED")
        m = material.xplane
        col = layout.column()
        col.prop(m, "draw", text="Visible")
        if not m.draw:
            col.label(text="Invisible, still clickable", icon="INFO")
        else:
            col.label(text="Transparency")
            row = col.row(align=True)
            for value, label in BLEND_LABELS:
                row.prop_enum(m, "blend_v1000", value, text=label)
            if m.blend_v1000 in (C.BLEND_OFF, C.BLEND_SHADOW):
                col.prop(m, "blendRatio", text="Cut Off Below", slider=True)
            col.prop(m, "shadow_local", text="Casts Shadows")
        col.prop(m, "solid_camera", text="Camera Cannot Pass Through")

        col.separator()
        _screen_layout(col, context, m)

        col.separator()
        col.prop(m, "lightLevel", text="Material Glow")
        if m.lightLevel:
            glow_layout(col.box().column(), m, "material:xplane.lightLevel_dataref")


class XPLANE_PT_surface_more(_MaterialTab, bpy.types.Panel):
    bl_label = "More"
    bl_parent_id = "XPLANE_PT_surface"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        m = context.material.xplane
        col = self.layout.column()
        col.prop(m, "surfaceType", text="Hard Surface")
        if m.surfaceType != C.SURFACE_TYPE_NONE:
            col.prop(m, "deck", text="Can Be Under It (deck)")
        col.prop(m, "poly_os", text="Draw On Top (polygon offset)")
        custom_lines_layout(col, m, "material:xplane", animation=False)


classes = (XPLANE_PT_surface, XPLANE_PT_surface_more)
