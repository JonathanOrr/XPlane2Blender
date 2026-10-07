"""
What the panels remember while Blender runs (not saved in the .blend), and which file they show.
"""

from typing import List, Optional

import bpy

from io_xplane2blender import xplane_helpers
from io_xplane2blender import xplane_inspector as I


class XPlaneCheckItem(bpy.types.PropertyGroup):
    object_name: bpy.props.StringProperty()
    text: bpy.props.StringProperty()


class XPlanePanelState(bpy.types.PropertyGroup):
    file_index: bpy.props.IntProperty(name="File", default=-1)
    show_all_collections: bpy.props.BoolProperty(
        name="All Collections",
        description="List every collection, so any of them can be made an export file",
        default=False,
    )
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
    checked: bpy.props.BoolProperty(default=False)
    check_items: bpy.props.CollectionProperty(type=XPlaneCheckItem)
    check_index: bpy.props.IntProperty()


def state(context) -> XPlanePanelState:
    return context.window_manager.xplane_panels


def active_file(context) -> Optional[I.FileOwner]:
    """The file the Export panel shows: the one picked in the list, otherwise the active object's"""
    scene = context.scene
    index = state(context).file_index
    if 0 <= index < len(bpy.data.collections):
        collection = bpy.data.collections[index]
        if I.is_file(collection) and collection in xplane_helpers.get_collections_in_scene(scene):
            return collection
    obj = context.object
    if obj is not None:
        owners = I.files_of(obj, scene)
        if owners:
            return owners[0]
    files = I.export_files(scene)
    return files[0] if files else None


def selected_or_active(context) -> List[bpy.types.Object]:
    objects = list(context.selected_objects)
    if context.object is not None and context.object not in objects:
        objects.append(context.object)
    return objects


def resolve(context, target: str):
    """
    'object:xplane.manip.command' -> (the active object's manip settings, 'command').
    The part before ':' is object, material, light, bone or file (the file the Export panel shows).
    """
    where, _, path = target.partition(":")
    obj = context.object
    base = {
        "object": obj,
        "material": obj.active_material if obj else None,
        "light": obj.data if obj is not None and obj.type == "LIGHT" else None,
        "bone": getattr(context, "bone", None) or getattr(context, "active_bone", None),
        "file": active_file(context),
    }[where]
    if base is None:
        return None, None
    parent, _, attr = path.rpartition(".")
    return (base.path_resolve(parent) if parent else base), attr


classes = (XPlaneCheckItem, XPlanePanelState)
