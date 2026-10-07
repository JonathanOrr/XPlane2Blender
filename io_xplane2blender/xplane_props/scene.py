"""
Settings of a Blender scene: how exports are logged, and the developer tools.
"""

import bpy

from .version import XPlane2BlenderVersion


class XPlaneSceneSettings(bpy.types.PropertyGroup):
    """bpy.types.Scene.xplane"""

    debug: bpy.props.BoolProperty(
        name="Print Debug Info To Output, OBJ",
        description="If checked debug information will be printed to the console and into OBJ files",
        default=False,
    )
    log: bpy.props.BoolProperty(
        name="Create Log File",
        description="If checked the debug information will be written to a log file",
        default=False,
    )
    optimize: bpy.props.BoolProperty(
        name="Optimize",
        description="If checked file size will be optimized. However this can increase export time slightly",
        default=False,
    )
    wiper_bake_start: bpy.props.IntProperty(
        name="Start Frame", description="Start of keyframe range for baking wiper gradient texture", min=1, default=1
    )

    plugin_development: bpy.props.BoolProperty(
        name="Developer Tools",
        description="Tools for people working on this add-on itself",
        default=False,
    )
    dev_enable_breakpoints: bpy.props.BoolProperty(
        name="Enable Breakpoints",
        description="Allows use of Eclipse breakpoints (must have PyDev, Eclipse installed and configured to use and"
        " Pydev Debug Server running!)",
        default=False,
    )
    dev_export_as_dry_run: bpy.props.BoolProperty(
        name="Dry Run", description="Run exporter without actually writing .objs to disk", default=False
    )
    dev_fake_xplane2blender_version: bpy.props.StringProperty(
        name="Fake XPlane2Blender Version",
        description="The Fake XPlane2Blender Version to re-run the upgrader with",
    )

    # Every version of the add-on the .blend file has been opened with, from the earliest
    xplane2blender_ver_history: bpy.props.CollectionProperty(
        name="XPlane2Blender History",
        description="Every version of XPlane2Blender this .blend file has been opened with",
        type=XPlane2BlenderVersion,
    )
