"""
Object tab, Light card: which X-Plane light a Blender light becomes, and its settings.
"""

from typing import Optional

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_light_tools
from io_xplane2blender.xplane_types.xplane_light import XPlaneLight
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as lights_txt

from .common import copy_button, custom_lines_layout, wrapped
from .light_params import parameters_layout
from .menus import XPLANE_MT_light_kind, light_kind_label
from .object_tab import Card
from .search import text_with_search

PARAM_PROPS = (
    ("INDEX", "param_index"),
    ("INTENSITY", "param_intensity_new"),
    ("FREQ", "param_freq"),
    ("PHASE", "param_phase"),
    ("SIZE", "param_size"),
)


def name_rows(layout, data) -> None:
    """The lights.txt name with a search button, and what that light is"""
    row = layout.row(align=True)
    row.prop(data.xplane, "name")
    row.operator("xplane.light_pick_name", text="", icon="VIEWZOOM")
    name = data.xplane.name.strip()
    if name:
        known = xplane_light_tools.is_known(name)
        wrapped(
            layout,
            xplane_light_tools.describe(name, with_params=False),
            "INFO" if known else "ERROR",
        )


def _cone_width(data, parsed) -> Optional[str]:
    """The cone the exporter writes for a library light, worked out from the spot size"""
    params = parsed.light_param_def
    if "WIDTH" not in params and "DIR_MAG" not in params:
        return None
    if data.type == "POINT":
        return "all around"
    if "DIR_MAG" in params:
        return f"{XPlaneLight.DIR_MAG_for_billboard(data.spot_size):.5g}"
    overload = parsed.best_overload().overload_type
    if (
        "BILLBOARD" in overload
        and parsed.name not in lights_txt.BILLBOARD_USES_SPILL_DXYZ
    ):
        return f"{XPlaneLight.WIDTH_for_billboard(data.spot_size):.5g}"
    return f"{XPlaneLight.WIDTH_for_spill(data.spot_size):.5g}"


def _library_light_layout(layout, data) -> None:
    name = data.xplane.name.strip()
    if not name:
        return
    try:
        parsed = lights_txt.get_parsed_light(name)
    except KeyError:
        return
    if not lights_txt.is_automatic_light_compatible(parsed.name):
        wrapped(
            layout,
            "This light cannot be a Library Light: use Library Light, By Name or Library Light, Manual.",
            "ERROR",
        )
        return
    if data.type not in ("POINT", "SPOT"):
        layout.label(text="Use a Point or Spot light", icon="ERROR")
        return
    try:
        omni = (
            data.type == "POINT"
            if "DIR_MAG" in parsed.light_param_def
            else parsed.best_overload().is_omni()
        )
    except ValueError:
        # Depends on the cone, which is filled in when exporting
        omni = None
    if omni and data.type == "SPOT":
        wrapped(layout, f"'{name}' shines all around: make it a Point light", "ERROR")
        return
    if omni is False and data.type == "POINT":
        wrapped(layout, f"'{name}' shines one way: make it a Spot light", "ERROR")
        return
    for param, prop in PARAM_PROPS:
        if param == "SIZE" and parsed.name in lights_txt.SIZE_AS_INTENSITY:
            prop = "param_intensity_new"
        if param in parsed.light_param_def:
            layout.prop(data.xplane, prop)
    width = _cone_width(data, parsed)
    if width is not None:
        layout.label(text=f"Cone written as: {width}", icon="LIGHT_SPOT")
    wrapped(
        layout,
        "Direction, color and cone are the Blender light's rotation, Color and Spot Size. Its Power is the Intensity"
        " while it is on, and its Custom Distance is the Light Size of a spill",
        "LINKED",
    )


class XPLANE_PT_light(Card, bpy.types.Panel):
    bl_label = "Light"
    bl_order = 1
    object_types = ("LIGHT",)

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "LIGHT")

    def draw(self, context):
        layout = self.layout
        data = context.object.data
        x = data.xplane
        layout.menu(
            XPLANE_MT_light_kind.bl_idname, text=light_kind_label(x.type), icon="LIGHT"
        )
        col = layout.column()
        if x.type == C.LIGHT_AUTOMATIC:
            name_rows(col, data)
            _library_light_layout(col, data)
        elif x.type == C.LIGHT_SPILL_CUSTOM:
            col.prop(x, "size", text="Reach (m)")
            wrapped(
                col,
                "Reach is the Blender light's Custom Distance, the cone its Spot Size",
                "LINKED",
            )
            text_with_search(
                col,
                x,
                "dataref",
                "Brightness Dataref",
                "dataref",
                "light:xplane.dataref",
            )
            col.prop(data, "color")
            col.prop(x, "spill_dim")
            if data.type == "SPOT":
                col.label(
                    text=f"Cone written as: {XPlaneLight.WIDTH_for_spill(data.spot_size):.5g}",
                    icon="LIGHT_SPOT",
                )
            elif data.type != "POINT":
                col.label(text="Use a Point or Spot light", icon="ERROR")
        elif x.type == C.LIGHT_CUSTOM:
            col.prop(x, "size")
            col.label(text="Texture Area")
            grid = col.grid_flow(row_major=True, columns=2, align=True)
            grid.use_property_split = False
            for i, side in enumerate(("Left", "Top", "Right", "Bottom")):
                grid.prop(x, "uv", index=i, text=side)
            text_with_search(
                col, x, "dataref", "Dataref", "dataref", "light:xplane.dataref"
            )
            col.prop(x, "enable_rgb_override", text="Type The Color")
            if x.enable_rgb_override:
                col.prop(x, "rgb_override_values", text="")
            else:
                col.prop(data, "color")
            col.prop(data, "energy", text="Alpha")
        elif x.type == C.LIGHT_NAMED:
            name_rows(col, data)
        elif x.type == C.LIGHT_PARAM:
            name_rows(col, data)
            parameters_layout(col, data)
            problem = xplane_light_tools.param_check(x.name, x.params)[1]
            if problem:
                col.label(text=problem, icon="ERROR")
        if x.type != C.LIGHT_NON_EXPORTING:
            layout.operator(
                xplane_light_tools.XPLANE_OT_lights_preview.bl_idname,
                text="Preview As In X-Plane",
                icon="SHADING_RENDERED",
            ).selected_only = True


class XPLANE_PT_light_more(Card, bpy.types.Panel):
    bl_label = "Light Lines"
    bl_parent_id = "XPLANE_PT_light"
    bl_options = {"DEFAULT_CLOSED"}
    object_types = ("LIGHT",)

    def draw(self, context):
        custom_lines_layout(
            self.layout, context.object.data.xplane, "light:xplane", animation=False
        )


classes = (XPLANE_PT_light, XPLANE_PT_light_more)
