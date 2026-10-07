# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####
import bpy

# Contains informations for Blender to recognize and categorize the addon.
bl_info = {
    "name": "X-Plane 12 Aircraft Tools",
    "description": "Build, import and export X-Plane 12 aircraft and cockpit objects (.obj). A fork of XPlane2Blender",
    "author": "Jonathan Orr; XPlane2Blender by Ted Greene, Ben Supnik, Amy Parent, Maya F. Eroğlu",
    "version": (5, 0, 0),
    "blender": (3, 6, 0),
    "location": "Properties > Object, Material, Collection and Scene tabs > X-Plane; File > Import/Export > X-Plane",
    "warning": "",
    "doc_url": "https://xp2b-docs.gitbook.io/xplane2blender-docs",
    "tracker_url": "https://github.com/JonathanOrr/XPlane2Blender/issues",
    "category": "Import-Export",
}

if "" not in locals():

    from . import xplane_props
    from . import xplane_export
    from . import xplane_ops
    from . import xplane_ops_wiper
    from . import xplane_ops_dev
    from . import xplane_bulk_edit
    from . import xplane_table
    from . import xplane_light_tools
    from . import xplane_anim_presets
    from . import ui
    from . import xplane_overlay
    from . import xplane_config
    from . import xplane_updater
    from .xplane_importer import ops as xplane_import_ops
    from .xplane_utils import xplane_lights_txt_parser
    from .xplane_utils import xplane_wiper_gradient
else:
    import importlib
    xplane_props   = importlib.reload(xplane_props)
    xplane_export  = importlib.reload(xplane_export)
    xplane_ops     = importlib.reload(xplane_ops)
    xplane_ops_wiper = importlib.reload(xplane_ops_wiper)
    xplane_ops_dev = importlib.reload(xplane_ops_dev)
    xplane_bulk_edit = importlib.reload(xplane_bulk_edit)
    xplane_table = importlib.reload(xplane_table)
    xplane_light_tools = importlib.reload(xplane_light_tools)
    xplane_anim_presets = importlib.reload(xplane_anim_presets)
    ui = importlib.reload(ui)
    xplane_overlay = importlib.reload(xplane_overlay)
    xplane_config  = importlib.reload(xplane_config)
    xplane_updater = importlib.reload(xplane_updater)
    xplane_import_ops = importlib.reload(xplane_import_ops)
    xplane_lights_txt_parser = importlib.reload(xplane_lights_txt_parser)
    xplane_wiper_gradient = importlib.reload(xplane_wiper_gradient)


# Function: menu_func
# Adds the export option to the menu.
#
# Parameters:
#   self - Instance to something
#   context - The Blender context object
def menu_func(self, context):
    self.layout.operator(
        xplane_export.EXPORT_OT_ExportXPlane.bl_idname, text="X-Plane Object (.obj)"
    )


# Function: register
# Registers the addon with all its classes and the menu function.
def register():
    xplane_export.register()
    xplane_props.register()
    xplane_ops.register()
    xplane_ops_wiper.register()
    xplane_ops_dev.register()
    ui.register()
    xplane_overlay.register()
    xplane_bulk_edit.register()
    xplane_table.register()
    xplane_light_tools.register()
    xplane_anim_presets.register()
    xplane_import_ops.register()
    bpy.types.TOPBAR_MT_file_export.append(menu_func)


# Function: unregister
# Unregisters the addon and all its classes and removes the entry from the menu.
def unregister():
    xplane_export.unregister()
    xplane_import_ops.unregister()
    xplane_anim_presets.unregister()
    xplane_light_tools.unregister()
    xplane_table.unregister()
    xplane_bulk_edit.unregister()
    xplane_overlay.unregister()
    ui.unregister()
    xplane_ops_wiper.unregister()
    xplane_ops.unregister()
    xplane_ops_dev.unregister()
    xplane_props.unregister()
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)


if __name__ == "__main__":
    register()
