"""set_ helpers, exportable roots and the test start file"""

import math
import os.path
import shutil
import typing
from collections import namedtuple
from pathlib import Path
from typing import *

import bpy
from mathutils import Euler, Quaternion, Vector

import io_xplane2blender
from io_xplane2blender import xplane_constants, xplane_helpers
from io_xplane2blender.xplane_constants import ANIM_TYPE_HIDE, ANIM_TYPE_SHOW
from io_xplane2blender.xplane_helpers import (
    ExportableRoot,
    PotentialRoot,
    XPlaneLogger,
    logger,
)
from io_xplane2blender.xplane_props import XPlaneManipulatorSettings
from io_xplane2blender.xplane_types import xplane_file

from .test_creation_infos import *
from .test_creation_infos import _ARMATURE, _BONE
from .test_creation_datablocks import *


def lookup_potential_root_from_name(name: str) -> PotentialRoot:
    """
    Attempts to find a Potential Root
    using the name of the collection or object

    Asserts that name is in bpy.data
    """
    assert isinstance(name, str), f"name must be a str, is {type(name)}"
    try:
        root_object = bpy.data.collections[name]
    except KeyError:
        try:
            root_object = bpy.data.objects[name]
        except KeyError:
            assert False, f"{name} must be in bpy.data.collections|objects"
    return root_object


def make_root_exportable(
    potential_root: Union[PotentialRoot, str],
    view_layer: Optional[bpy.types.ViewLayer] = None,
) -> ExportableRoot:
    """
    Makes a root, as given or as found by it's name from collections then root objects,
    meet the criteria for exportable - not disabled in viewport, not hidden in viewport, and checked Exportable.

    Returns that changed ExportableRoot
    """
    view_layer = view_layer or bpy.context.scene.view_layers[0]
    if isinstance(potential_root, str):
        potential_root = lookup_potential_root_from_name(potential_root)

    if isinstance(potential_root, bpy.types.Collection):
        potential_root.xplane.is_exportable_collection = True
        # This is actually talking about "Visibile In Viewport" - the little eyeball
        all_layer_collections = {
            lc.name: lc
            for lc in xplane_helpers.get_layer_collections_in_view_layer(view_layer)
        }
        all_layer_collections[potential_root.name].hide_viewport = False
    elif isinstance(potential_root, bpy.types.Object):
        potential_root.xplane.isExportableRoot = True
        # This is actually talking about "Visibile In Viewport" - the little eyeball
        potential_root.hide_set(False, view_layer=view_layer)
    else:
        assert False, "How did we get here?!"

    # This is actually talking about "Disable In Viewport"
    potential_root.hide_viewport = False
    return potential_root


def make_root_unexportable(
    exportable_root: Union[ExportableRoot, str],
    view_layer: Optional[bpy.types.ViewLayer] = None,
    hide_viewport: bool = False,
    disable_viewport: bool = False,
) -> ExportableRoot:
    """
    Makes a root, unexportable, and optionally, some type of
    hidden in the viewport. By default we just do the
    minimum - turning off exportablity
    """
    view_layer = view_layer or bpy.context.scene.view_layers[0]
    if isinstance(exportable_root, str):
        exportable_root = lookup_potential_root_from_name(exportable_root)

    if isinstance(exportable_root, bpy.types.Collection):
        exportable_root.xplane.is_exportable_collection = False
        # This is actually talking about "Visible In Viewport" - the little eyeball
        all_layer_collections = {
            lc.name: lc
            for lc in xplane_helpers.get_layer_collections_in_view_layer(view_layer)
        }
        all_layer_collections[exportable_root.name].hide_viewport = True
    elif isinstance(exportable_root, bpy.types.Object):
        exportable_root.xplane.isExportableRoot = True
        # This is actually talking about "Visible In Viewport" - the little eyeball
        exportable_root.hide_set(disable_viewport)
    else:
        assert False, "How did we get here?!"


def set_animation_data(
    blender_struct: Union[bpy.types.Object, bpy.types.Bone, bpy.types.PoseBone],
    keyframe_infos: List[KeyframeInfo],
    parent_armature: [bpy.types.Armature] = None,
) -> None:
    """
    - blender_struct - A Blender light, mesh, armature, or bone to attach keyframes to. For a bone, pass it
    in (excluding EditBones) and the function will take care of choosing between Bone and EditBone as needed
    - keyframe_infos - A list of keyframe info which will be used to apply keyframes
    - parent_armature - If the blender_struct is a Bone but not a PoseBone, the parent armature of it is required
    (because Bones do not keep track of who their parent armature is for some reason -Ted, 3/21/2018)

    keyframe_infos must be all the same dataref and all the same animation type. This was a deliberate choice
    to help catch errors in bad data
    """

    # Ensure each call to set_animation_data has the same dataref_path and anim_type
    # for each KeyframeInfo
    assert len({kf_info.dataref_path for kf_info in keyframe_infos}) == 1
    assert len({kf_info.dataref_anim_type for kf_info in keyframe_infos}) == 1

    if (
        keyframe_infos[0].dataref_anim_type == xplane_constants.ANIM_TYPE_SHOW
        or keyframe_infos[0].dataref_anim_type == xplane_constants.ANIM_TYPE_HIDE
    ):
        value = keyframe_infos[0].dataref_value
        value_1 = keyframe_infos[0].dataref_show_hide_v1
        value_2 = keyframe_infos[0].dataref_show_hide_v2
        assert value is None and value_1 is not None and value_2 is not None
    if keyframe_infos[0].dataref_anim_type == xplane_constants.ANIM_TYPE_TRANSFORM:
        value = keyframe_infos[0].dataref_value
        value_1 = keyframe_infos[0].dataref_show_hide_v1
        value_2 = keyframe_infos[0].dataref_show_hide_v2
        assert value is not None and value_1 is None and value_2 is None

    struct_is_bone = False
    if isinstance(blender_struct, bpy.types.Bone) or isinstance(
        blender_struct, bpy.types.PoseBone
    ):
        assert parent_armature is not None
        try:
            blender_bone = parent_armature.data.bones[blender_struct.name]
            blender_pose_bone = parent_armature.pose.bones[blender_struct.name]
            blender_struct = blender_pose_bone
            struct_is_bone = True
        except:
            assert False, "{} is not a pose bone in parent_armature {}".format(
                blender_struct.name, parent_armature.name
            )

    if struct_is_bone:
        datarefs = blender_bone.xplane.datarefs
    else:
        datarefs = blender_struct.xplane.datarefs
    # If this dataref has never been added before, add it. Otherwise,
    # find the index in the xplane.datarefs collection
    if not keyframe_infos[0].dataref_path in [dref.path for dref in datarefs]:
        dataref_prop = datarefs.add()
        dataref_prop.path = keyframe_infos[0].dataref_path
        dataref_prop.anim_type = keyframe_infos[0].dataref_anim_type
        dataref_index = len(datarefs) - 1
    else:
        dataref_index = 0
        for dref in datarefs:
            if dref.path == keyframe_infos[0].dataref_path:
                dataref_prop = dref
                break
            dataref_index += 1

    for kf_info in keyframe_infos:
        bpy.context.scene.frame_set(kf_info.idx)

        if (
            kf_info.dataref_anim_type == ANIM_TYPE_SHOW
            or kf_info.dataref_anim_type == ANIM_TYPE_HIDE
        ):
            dataref_prop.show_hide_v1 = kf_info.dataref_show_hide_v1
            dataref_prop.show_hide_v2 = kf_info.dataref_show_hide_v2
        else:
            dataref_prop.value = kf_info.dataref_value

        if not kf_info.location and not kf_info.rotation:
            continue

        if kf_info.location:
            blender_struct.location = kf_info.location
            blender_struct.keyframe_insert(
                data_path="location",
                group=blender_struct.name if struct_is_bone else "Location",
            )
        if kf_info.rotation:
            blender_struct.rotation_mode = kf_info.rotation_mode
            data_path = "rotation_{}".format(kf_info.rotation_mode.lower())

            if kf_info.rotation_mode == "AXIS_ANGLE":
                blender_struct.rotation_axis_angle = (
                    kf_info.rotation[0],
                    *kf_info.rotation[1],
                )
            elif kf_info.rotation_mode == "QUATERNION":
                blender_struct.rotation_quaternion = kf_info.rotation[:]
            else:
                data_path = "rotation_euler"
                blender_struct.rotation_euler = [
                    math.radians(r) for r in kf_info.rotation[:]
                ]
            blender_struct.keyframe_insert(
                data_path=data_path,
                group=blender_bone.name if struct_is_bone else "Rotation",
            )

        if struct_is_bone:
            bpy.context.view_layer.objects.active = parent_armature
            bpy.context.view_layer.objects.active.data.bones.active = blender_bone
            bpy.ops.bone.add_xplane_dataref_keyframe(index=dataref_index)
        else:
            bpy.context.view_layer.objects.active = blender_struct
            with bpy.context.temp_override(object=blender_struct):
                bpy.ops.object.add_xplane_dataref_keyframe(index=dataref_index)
                

def set_collection(
    blender_object: bpy.types.Object, collection: Union[bpy.types.Collection, str]
) -> None:
    """
    Links a datablock in collection. If collection is a string and does not exist, one will be made.

    Remember to unlink blender_objects from other collections by hand if needed
    """
    assert isinstance(
        blender_object, (bpy.types.Object)
    ), "collection was of type " + str(type(blender_object))

    if isinstance(collection, bpy.types.Collection):
        coll = collection
    else:
        coll = create_datablock_collection(collection)

    if blender_object.name not in coll.objects:
        coll.objects.link(blender_object)


def set_manipulator_settings(
    object_datablock: bpy.types.Object,
    manip_type: str,
    manip_enabled: bool = True,
    manip_props: Optional[Dict[str, Any]] = None,
):
    """
    manip_type and manip_enabled, since they're the most common.
    if manip_props is left none, defaults for Cursor and Tooltip will be filled in
    using the object's name
    """
    assert object_datablock.type == "MESH"
    if manip_props is None:
        manip_props = {}

    object_datablock.xplane.manip.type = manip_type
    object_datablock.xplane.manip.enabled = manip_enabled
    if manip_enabled is False:
        return

    if "cursor" not in manip_props:
        manip_props["cursor"] = "hand"
    if "tooltip" not in manip_props:
        manip_props["tooltip"] = "{} type manipulator on {}".format(
            manip_type, object_datablock.name
        )

    for prop_name, value in manip_props.items():
        attr = getattr(object_datablock.xplane.manip, prop_name, None)
        assert attr is not None, "{} is not a real manip property!".format(prop_name)

        if prop_name == "axis_detent_ranges":
            for item in value:
                new_axis_detent_range = attr.add()
                new_axis_detent_range.start = item.start
                new_axis_detent_range.end = item.end
                new_axis_detent_range.height = item.height
        else:
            setattr(object_datablock.xplane.manip, prop_name, value)


def set_material(
    blender_object: bpy.types.Object,
    material_name: str = "Material",
    material_props: Optional[Dict[str, Any]] = None,
    create_missing: bool = True,
):

    mat = create_material(material_name)
    try:
        blender_object.material_slots[0].material = mat
    except IndexError:
        blender_object.data.materials.append(mat)
    if material_props:
        for prop, value in material_props.items():
            setattr(mat.xplane.manip, prop, value)


def set_parent(blender_object: bpy.types.Object, parent_info: ParentInfo) -> None:
    assert isinstance(blender_object, bpy.types.Object)

    blender_object.parent = parent_info.parent
    blender_object.parent_type = parent_info.parent_type

    if parent_info.parent_type == _BONE:
        assert (
            parent_info.parent.type == _ARMATURE
            and parent_info.parent.data.bones.get(parent_info.parent_bone) is not None
        )

        blender_object.parent_bone = parent_info.parent_bone


def set_rotation(
    blender_object: bpy.types.Object, rotation: Any, rotation_mode: str
) -> None:
    """
    Sets the rotation of a Blender Object and takes care of picking which
    rotation type to give the value to
    """
    if rotation_mode == "AXIS_ANGLE":
        assert len(rotation[1]) == 3
        blender_object.rotation_axis_angle = rotation
    elif rotation_mode == "QUATERNION":
        assert len(rotation) == 4
        blender_object.rotation_quaternion = rotation
    elif set(rotation_mode) == {"X", "Y", "Z"}:
        assert len(rotation) == 3
        blender_object.rotation_euler = rotation
    else:
        assert False, "Unsupported rotation mode: " + blender_object.rotation_mode


def set_xplane_layer(
    layer: Union[int, io_xplane2blender.xplane_props.XPlaneLayer],
    layer_props: Dict[str, Any],
):
    assert isinstance(layer, int) or isinstance(
        layer, io_xplane2blender.xplane_props.XPlaneLayer
    )

    if isinstance(layer, int):
        layer = create_datablock_collection(f"Layer {layer + 1}").xplane.layer

    for prop, value in layer_props.items():
        setattr(layer, prop, value)


class TemporaryStartFile:
    def __init__(self, temporary_startup_path: str):
        self.temporary_startup_path = temporary_startup_path

    def __enter__(self) -> None:
        real_startup_filepath = os.path.join(
            bpy.utils.user_resource("CONFIG"), "startup.blend"
        )
        try:
            os.replace(real_startup_filepath, real_startup_filepath + ".bak")
        except FileNotFoundError as e:
            print(e)
            raise
        else:
            shutil.copyfile(self.temporary_startup_path, real_startup_filepath)
        bpy.ops.wm.read_homefile()

    def __exit__(self, type, value, traceback) -> None:
        real_startup_filepath = os.path.join(
            bpy.utils.user_resource("CONFIG"), "startup.blend"
        )
        os.replace(real_startup_filepath + ".bak", real_startup_filepath)
        return False


def create_initial_test_setup():
    bpy.ops.wm.read_homefile()
    delete_everything()
    xplane_file._all_keyframe_infos.clear()
    logger.clear()
    logger.addTransport(
        xplane_helpers.XPlaneLogger.InternalTextTransport(),
        xplane_constants.LOGGER_LEVELS_ALL,
    )
    logger.addTransport(XPlaneLogger.ConsoleTransport())
    create_material_default()

    # Create text file
    header_str = "Unit Test Overview"
    try:
        unit_test_overview = bpy.data.texts[header_str]
    except KeyError:
        unit_test_overview = bpy.data.texts.new(header_str)
    finally:
        unit_test_overview.write(header_str + "\n\n")

    # bpy.ops.console.insert(text="bpy.ops.export.xplane_obj()")
