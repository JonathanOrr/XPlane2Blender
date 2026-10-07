import itertools
import os
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import bpy
import mathutils

from io_xplane2blender.xplane_constants import PRECISION_OBJ_FLOAT

if TYPE_CHECKING:
    from io_xplane2blender.xplane_types import xplane_file

"""
Given the difficulty in keeping all these words straight, these
types have been created. Use these to keep yourself from
running in circles
"""

"""Something with an XPlaneLayer property"""
PotentialRoot = Union[bpy.types.Collection, bpy.types.Object]

"""
Something with an XPlaneLayer property that also meets all other requirements.
It does not garuntee an error or warning free export, however
"""
ExportableRoot = Union[bpy.types.Collection, bpy.types.Object]

"""
Something that has a .children property. A collection and object's
children are not compatible
"""
BlenderParentType = Union[bpy.types.Collection, bpy.types.Object]


class UnwriteableXPlaneType(ValueError):
    pass


MULTIPLAYER_DATAREF_PREFIX = "sim/multiplayer/"


def is_multiplayer_dataref(dataref_path: str) -> bool:
    """
    sim/multiplayer datarefs must not be used in objects. Datarefs.txt always
    lists them, so they are only rejected when actually used as an animation
    dataref (see XPlaneObject.collectAnimAttributes / XPlaneBone.collectAnimations)
    """
    return dataref_path.startswith(MULTIPLAYER_DATAREF_PREFIX)


def floatToStr(n: float) -> str:
    """
    Makes a rounded float with as 0's
    and decimal place removed if possible
    """
    # THIS IS A HOT PATH, DO NOT CHANGE WITHOUT PROFILING

    # 'g' can do the rstrip and '.' removal for us, except for rare cases when we need to fallback
    # to the less fast 'f', rstrip, ternary approach
    s = f"{n:.{PRECISION_OBJ_FLOAT}g}"
    if "e" in s:
        s = f"{n:.{PRECISION_OBJ_FLOAT}f}".rstrip("0")
        return s if s[-1] != "." else s[:-1]
    return s


def resolveBlenderPath(path: str) -> str:
    blenddir = os.path.dirname(bpy.context.blend_data.filepath)

    if path[0:2] == "//":
        return os.path.join(blenddir, path[2:])
    else:
        return path


def effective_normal_metalness(xp_file: "xplane_file.XPlaneFile") -> bool:
    return xp_file.options.normal_metalness


def is_path_decal_lib(file_path: str) -> bool:
    return Path(file_path).suffix.lower() == ".dcl"


def get_plugin_resources_folder() -> str:
    return os.path.join(os.path.dirname(__file__), "resources")


def get_potential_objects_in_exportable_root(
    root: PotentialRoot,
) -> List[bpy.types.Object]:
    def is_potential_child(obj: bpy.types.Object) -> bool:
        return obj.type in {"MESH", "LIGHT", "ARMATURE", "EMPTY"}

    def collect_children(obj: bpy.types.Object) -> List[bpy.types.Object]:
        objects = []  # type: List[bpy.types.Object]
        for child in obj.children:
            if is_potential_child(child):
                objects.append(child)
            objects.extend(collect_children(child))
        return objects

    if isinstance(root, bpy.types.Object):
        return collect_children(root)
    else:
        return [obj for obj in root.all_objects if is_potential_child(obj)]


def get_rotation_from_rotatable(
    obj_or_bone: Union[bpy.types.Object, bpy.types.PoseBone],
) -> Union[mathutils.Euler, mathutils.Quaternion, Tuple[float, float, float, float]]:
    """Returns a copy of the rotation, in whatever mode was given"""
    rotation_mode = obj_or_bone.rotation_mode

    if rotation_mode == "QUATERNION":
        return obj_or_bone.rotation_quaternion.copy()
    elif rotation_mode == "AXIS_ANGLE":
        return tuple(obj_or_bone.rotation_axis_angle)
    else:
        return obj_or_bone.rotation_euler.copy()


def get_collections_in_scene(scene: bpy.types.Scene) -> List[bpy.types.Collection]:
    """
    First entry in list is always the scene's 'Master Collection'
    """

    def get_collections_from_collection(
        collection: bpy.types.Collection,
    ) -> List[bpy.types.Collection]:
        collections = []
        for child in collection.children:
            collections.append(child)
            collections.extend(get_collections_from_collection(child))

        return collections

    return [scene.collection] + get_collections_from_collection(scene.collection)


def get_layer_collections_in_view_layer(
    view_layer: bpy.types.ViewLayer,
) -> List[bpy.types.LayerCollection]:
    """
    First entry in list is always the scene's Master Layer Collection
    """

    def get_layer_collections_from_layer_collection(
        layer_collection: bpy.types.LayerCollection,
    ) -> List[bpy.types.LayerCollection]:
        child_lcs = []
        for child_lc in layer_collection.children:
            child_lcs.append(child_lc)
            child_lcs.extend(get_layer_collections_from_layer_collection(child_lc))
        return child_lcs

    return [view_layer.layer_collection] + get_layer_collections_from_layer_collection(
        view_layer.layer_collection
    )


def get_exportable_roots_in_scene(
    scene: bpy.types.Scene, view_layer: bpy.types.ViewLayer
) -> List[bpy.types.Object]:
    return [
        root
        for root in filter(
            lambda o: is_exportable_root(o, view_layer),
            itertools.chain(get_collections_in_scene(scene), scene.objects),
        )
    ]


def is_visible_in_viewport(
    datablock: Union[bpy.types.Collection, bpy.types.Object],
    view_layer: bpy.types.ViewLayer,
) -> Optional[ExportableRoot]:
    if isinstance(datablock, bpy.types.Collection):
        all_layer_collections = {
            c.name: c for c in get_layer_collections_in_view_layer(view_layer)
        }
        return all_layer_collections[datablock.name].is_visible
    elif isinstance(datablock, bpy.types.Object):
        return datablock.visible_get() or None


def is_exportable_root(
    potential_root: PotentialRoot, view_layer: bpy.types.ViewLayer
) -> bool:
    """
    Since datablocks don't keep track of which view layers they're a part of,
    we have to provide it
    """
    return (
        potential_root.xplane.get("isExportableRoot")
        or potential_root.xplane.get("is_exportable_collection")
    ) and is_visible_in_viewport(potential_root, view_layer)


def get_active_export_root(
    active_object: Optional[bpy.types.Object],
    collection: Optional[bpy.types.Collection],
) -> Optional[Union[bpy.types.Object, bpy.types.Collection]]:
    """
    Returns the exportable root the active context should use, or None when
    neither the active object nor the collection is exportable
    """
    if active_object is not None and active_object.xplane.isExportableRoot:
        return active_object
    if collection is not None and collection.xplane.is_exportable_collection:
        return collection
    return None


def round_vec(v: mathutils.Vector, ndigits: int) -> mathutils.Vector:
    return mathutils.Vector(round(comp, ndigits) for comp in v)


def vec_b_to_x(v) -> mathutils.Vector:
    return mathutils.Vector((v[0], v[2], -v[1]))


def vec_x_to_b(v) -> mathutils.Vector:
    return mathutils.Vector((v[0], -v[2], v[1]))


def material_nodes(material: Optional[bpy.types.Material]) -> Optional[bpy.types.NodeTree]:
    """The material's shader nodes when it uses them. Blender 5 always does, and deprecates use_nodes"""
    if material is None or material.node_tree is None:
        return None
    if bpy.app.version < (5, 0, 0) and not material.use_nodes:
        return None
    return material.node_tree


def get_action_fcurves(id_data: bpy.types.ID) -> List[bpy.types.FCurve]:
    """
    Returns the FCurves animating id_data through its assigned Action,
    or an empty list if there are none.

    Blender 4.4 introduced slotted Actions and 5.0 removed Action.fcurves,
    so on those versions the FCurves live in the assigned slot's channelbag.
    """
    channelbag = get_action_channelbag(id_data)
    if channelbag is not None:
        return list(channelbag.fcurves)

    anim_data = getattr(id_data, "animation_data", None)
    if anim_data is None or anim_data.action is None:
        return []
    return list(getattr(anim_data.action, "fcurves", []))


def get_action_channelbag(
    id_data: bpy.types.ID,
) -> Optional["bpy.types.ActionChannelbag"]:
    """
    Returns the channelbag of id_data's assigned Action slot (Blender 4.4+),
    or None if there isn't one or this Blender doesn't have slotted Actions
    """
    anim_data = getattr(id_data, "animation_data", None)
    if anim_data is None or anim_data.action is None:
        return None
    try:
        from bpy_extras.anim_utils import action_get_channelbag_for_slot
    except ImportError:
        return None
    return action_get_channelbag_for_slot(anim_data.action, anim_data.action_slot)


def remove_action_fcurve(id_data: bpy.types.ID, fcurve: bpy.types.FCurve) -> None:
    """Removes an FCurve returned by get_action_fcurves(id_data)"""
    channelbag = get_action_channelbag(id_data)
    if channelbag is not None:
        channelbag.fcurves.remove(fcurve)
    else:
        id_data.animation_data.action.fcurves.remove(fcurve)


def get_all_actions_fcurves() -> List[bpy.types.FCurve]:
    """Returns every FCurve of every Action in the file, for any slot"""
    fcurves = []
    for action in bpy.data.actions:
        if getattr(action, "layers", None):
            for layer in action.layers:
                for strip in layer.strips:
                    for channelbag in strip.channelbags:
                        fcurves.extend(channelbag.fcurves)
        else:
            fcurves.extend(getattr(action, "fcurves", []))
    return fcurves


# The version and the logger live in their own modules; much of the add-on reads them from here
from .xplane_logger import (  # noqa: E402,F401
    UnfinishedWork,
    XPlaneLogger,
    logger,
    unfinished,
)
from .xplane_version_struct import VerStruct  # noqa: E402,F401
