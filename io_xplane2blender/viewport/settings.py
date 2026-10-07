"""
What the X-Plane overlays and gizmos show. Kept on each screen, like Blender's own overlay settings, so the
X-Plane workspace keeps them on while other workspaces stay plain. Never exported.
"""

from typing import Optional

import bpy


class XPlaneViewSettings(bpy.types.PropertyGroup):
    show_click_zones: bpy.props.BoolProperty(
        name="Click Zones",
        description="Outline what can be clicked in X-Plane: orange runs commands, blue sets datarefs, green is dragged",
        default=False,
    )
    click_labels: bpy.props.EnumProperty(
        name="Click Labels",
        description="Say what clicking each object does",
        items=(
            ("OFF", "No Labels", "No labels"),
            ("SELECTED", "Labels: Selected", "Label the selected clickable objects"),
            ("ALL", "Labels: All", "Label every clickable object"),
        ),
        default="OFF",
    )
    show_motion: bpy.props.BoolProperty(
        name="Motion",
        description="Show how the selected animated objects move: their path from the first to the last keyframe,"
        " with the dataref value at each keyframe",
        default=False,
    )
    show_lever: bpy.props.BoolProperty(
        name="Lever Handle",
        description="A handle on the active animated object: drag it to move the part through its animation the way"
        " it moves in X-Plane, and read the dataref value",
        default=False,
    )
    show_lights: bpy.props.BoolProperty(
        name="Lights",
        description="Mark every X-Plane light in its color and name the selected ones",
        default=False,
    )
    show_unfinished: bpy.props.BoolProperty(
        name="Unfinished",
        description="Outline in red what the last Check listed as not filled in yet",
        default=False,
    )


def view_settings(context) -> Optional[XPlaneViewSettings]:
    """The settings of the screen being drawn, or None where there is no screen (background mode)"""
    return getattr(getattr(context, "screen", None), "xplane_view", None)


def register():
    bpy.utils.register_class(XPlaneViewSettings)
    bpy.types.Screen.xplane_view = bpy.props.PointerProperty(type=XPlaneViewSettings)


def unregister():
    del bpy.types.Screen.xplane_view
    bpy.utils.unregister_class(XPlaneViewSettings)
