"""
The X-Plane panels of the Properties editor, each in the tab it belongs to, following the selection:

- Object tab: what the active object is, which file it exports in, what is unfinished, and a card for each
  thing it can do (Clickable, Light, Attachment Point, Moves, Shows / Hides, Glow, Advanced)
- Bone tab: Moves and Shows / Hides of armature bones
- Material tab: how surfaces with the material are drawn, and whether they are a screen
- Collection tab: whether the collection is an OBJ file
- Scene tab: the OBJ files with one Export button and the picked file's settings, Unfinished Work, Tools

Plus X-Plane entries in the 3D View's Add and right-click menus.
"""

import bpy

from . import (
    common,
    file_panels,
    light_card,
    light_params,
    material_tab,
    menus,
    motion,
    object_tab,
    ops_file,
    ops_object,
    scene_tab,
    search,
    state,
)

# Parents before their child panels
_classes = (
    *state.classes,
    *search.classes,
    *common.classes,
    *ops_object.classes,
    *ops_file.classes,
    *menus.classes,
    *object_tab.classes,
    *light_params.classes,
    *light_card.classes,
    *motion.classes,
    *material_tab.classes,
    *scene_tab.classes,
    *file_panels.classes,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.xplane_panels = bpy.props.PointerProperty(type=state.XPlanePanelState)
    bpy.types.Light.xplane_params = bpy.props.PointerProperty(type=light_params.XPlaneLightParams)
    bpy.types.VIEW3D_MT_add.append(menus.add_menu_entry)
    bpy.types.VIEW3D_MT_object_context_menu.append(menus.context_menu_entry)


def unregister():
    bpy.types.VIEW3D_MT_object_context_menu.remove(menus.context_menu_entry)
    bpy.types.VIEW3D_MT_add.remove(menus.add_menu_entry)
    del bpy.types.Light.xplane_params
    del bpy.types.WindowManager.xplane_panels
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
