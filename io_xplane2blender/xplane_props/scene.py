"""
Settings of a Blender scene: how exports are logged, and the developer tools.
"""

import bpy

from .version import XPlane2BlenderVersion


class XPlaneSceneSettings(bpy.types.PropertyGroup):
    """bpy.types.Scene.xplane"""

    debug: bpy.props.BoolProperty(
        name="Print Debug Info To Output, OBJ",
        description="Write debug comments into the OBJs, and debug information to the console",
        default=False,
    )
    log: bpy.props.BoolProperty(
        name="Create Log File",
        description="Also write the debug information to a log file",
        default=False,
    )
    optimize: bpy.props.BoolProperty(
        name="Optimize",
        description="Write each vertex once per file, for smaller OBJs. Normals that differ only by Blender's rounding"
        " are merged",
        default=False,
    )
    wiper_bake_start: bpy.props.IntProperty(
        name="Start Frame", description="The first frame of the wiper animation to bake. The bake uses 255 frames", min=1, default=1
    )

    plugin_development: bpy.props.BoolProperty(
        name="Developer Tools",
        description="Tools for people working on this add-on itself",
        default=False,
    )
    dev_enable_breakpoints: bpy.props.BoolProperty(
        name="Enable Breakpoints",
        description="Stop at breakpoints in a running PyDev debug server (Eclipse with PyDev)",
        default=False,
    )
    dev_export_as_dry_run: bpy.props.BoolProperty(
        name="Dry Run", description="Run the export without writing the OBJs", default=False
    )
    dev_fake_xplane2blender_version: bpy.props.StringProperty(
        name="Fake XPlane2Blender Version",
        description="Re-run the updater as if the file was last saved by this version",
    )

    # Every version of the add-on the .blend file has been opened with, from the earliest
    xplane2blender_ver_history: bpy.props.CollectionProperty(
        name="XPlane2Blender History",
        description="Every version of XPlane2Blender this .blend file has been opened with",
        type=XPlane2BlenderVersion,
    )
