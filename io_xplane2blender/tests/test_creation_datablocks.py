"""create_, get_ and delete_ helpers for Blender datablocks"""

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


def create_bone(armature: bpy.types.Object, bone_info: BoneInfo) -> str:
    """
    Since, in Blender, Bones have a number of representations, here we pass back the final name of the new bone
    which can be used with data.edit_bones,data.bones,and pose.bones. The final name may not be the name inside
    new_bone.name
    """
    assert armature.type == "ARMATURE"
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="EDIT", toggle=False)
    edit_bones = armature.data.edit_bones
    new_bone = edit_bones.new(bone_info.name)
    new_bone.head = bone_info.head
    new_bone.tail = bone_info.tail
    if len(armature.data.bones) > 0:
        assert bone_info.parent in edit_bones
        print("bone_info.parent = {}".format(bone_info.parent))
        new_bone.parent = edit_bones[bone_info.parent]
    else:
        new_bone.parent = None

    # Keeping old references around crashing Blender
    final_name = new_bone.name
    bpy.ops.object.mode_set(mode="OBJECT")

    return final_name


def create_datablock_collection(
    name: str,
    scene: Optional[Union[str, bpy.types.Scene]] = None,
    parent: Optional[Union[bpy.types.Collection, str]] = None,
) -> bpy.types.Collection:
    """
    If already existing, return it. If not, creates a collection
    with the name provided. It can be linked to a scene and a parent
    other that that scene's Master Collection. (Parent must be in scene as well.)

    Otherwise, the context's scene and Master Collection is used for linking.
    """
    try:
        coll: bpy.types.Collection = bpy.data.collections[name]
    except (KeyError, TypeError):
        coll: bpy.types.Collection = bpy.data.collections.new(name)
    try:
        scene: bpy.types.Scene = bpy.data.scenes[scene]
    except (KeyError, TypeError):  # scene is str and not found or is None
        scene: bpy.types.Scene = bpy.context.scene
    try:
        parent: bpy.types.Collection = bpy.data.collections[parent]
    except (KeyError, TypeError):  # parent is str and not found or is Collection
        parent: bpy.types.Collection = scene.collection

    if coll.name not in parent.children:
        parent.children.link(coll)

    return coll


def create_datablock_armature(
    info: DatablockInfo,
    extra_bones: Optional[Union[List[BoneInfo], int]] = None,
    bone_direction: Optional[Vector] = None,
) -> bpy.types.Object:
    """
    Creates an armature datablock with (optional) extra bones.
    Extra bones can come in the form of a list of BoneInfos you want created and parented or
    a number of bones and a unit vector in the direction you want them grown in
    When using extra_bones, the intial armature bone's data is replaced by the first bone

    1. extra_bones=None and bone_direction=None
        Armature (uses defaults armature) of bpy.)
        |_Bone
    2. Using extra_bones:List[BoneInfo]
        Armature
        |_extra_bones[0]
            |_extra_bones[1]
                |_extra_bones[2]
                    |_... (parent data given in each bone and can be different than shown)
    3. Using extra_bones:int and bone_direction
        Armature                                                               [Armature]
        |_new_bone_0                                                          / extra_bones = 3
            |_new_bone_1                                                     /  bone_direction = (-1,-1, 0)
                |_new_bone_2                                                /
                    |_new_bone_... (where each bone is in a straight line) v
    """
    assert info.datablock_type == "ARMATURE"
    bpy.ops.object.armature_add(
        enter_editmode=False, location=info.location, rotation=info.rotation
    )
    arm = bpy.context.object
    arm.name = info.name if info.name is not None else arm.name
    arm.rotation_mode = info.rotation_mode
    arm.scale = info.scale

    if info.parent_info:
        set_parent(arm, info.parent_info)

    parent_name = ""
    if extra_bones:
        bpy.ops.object.mode_set(mode="EDIT", toggle=False)
        arm.data.edit_bones.remove(arm.data.edit_bones[0])
        bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

    if extra_bones and bone_direction:
        assert (
            isinstance(extra_bones, int)
            and isinstance(bone_direction, Vector)
            and bone_direction != Vector()
        )

        head = Vector((0, 0, 0))
        for extra_bone_counter in range(extra_bones):
            tail = head + bone_direction
            parent_name = create_bone(
                arm,
                BoneInfo("bone_{}".format(extra_bone_counter), head, tail, parent_name),
            )
            head += bone_direction

    if extra_bones and not bone_direction:
        assert isinstance(extra_bones, list) and isinstance(extra_bones[0], BoneInfo)
        for extra_bone in extra_bones:
            create_bone(arm, extra_bone)

    return arm


def create_datablock_empty(
    info: DatablockInfo, scene: Optional[Union[bpy.types.Scene, str]] = None,
) -> bpy.types.Object:
    """
    Creates a datablock empty and links it to a scene and collection.
    If scene is None, the current context's scene is used.
    """
    assert info.datablock_type == "EMPTY"
    ob = bpy.data.objects.new(info.name, object_data=None)
    try:
        scene = bpy.data.scenes[scene]
    except (KeyError, TypeError):
        scene = bpy.context.scene
    set_collection(ob, info.collection)

    ob.empty_display_type = "PLAIN_AXES"
    ob.location = info.location
    ob.rotation_mode = info.rotation_mode
    set_rotation(ob, info.rotation, info.rotation_mode)
    ob.scale = info.scale

    if info.parent_info:
        set_parent(ob, info.parent_info)

    return ob


def create_datablock_mesh(
    info: DatablockInfo,
    primitive_shape: str = "cube",
    material_name: Union[bpy.types.Material, str] = "Material",
    scene: Optional[Union[bpy.types.Scene, str]] = None,
) -> bpy.types.Object:
    """
    Uses the bpy.ops.mesh.primitive_*_add ops to create an Object with given
    mesh. Location and Rotation given by info.

    primitive_shape must match an existing mesh op
    """

    assert info.datablock_type == "MESH"
    assert primitive_shape in {
        "circle",
        "cone",
        "cube",
        "cylinder",
        "grid",
        "ico_sphere",
        "monkey",
        "plane",
        "torus",
        "uv_sphere",
    }

    primitive_ops: Dict[str, bpy.types.Operator] = {
        "circle": bpy.ops.mesh.primitive_circle_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "cube": bpy.ops.mesh.primitive_cube_add,
        "cylinder": bpy.ops.mesh.primitive_cylinder_add,
        "grid": bpy.ops.mesh.primitive_grid_add,
        "ico_sphere": bpy.ops.mesh.primitive_ico_sphere_add,
        "monkey": bpy.ops.mesh.primitive_monkey_add,
        "plane": bpy.ops.mesh.primitive_plane_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
        "uv_sphere": bpy.ops.mesh.primitive_uv_sphere_add,
    }

    try:
        op = primitive_ops[primitive_shape]
    except KeyError:
        assert False, f"{primitive_shape} is not a known primitive op"
    else:
        op(enter_editmode=False, location=info.location, rotation=info.rotation)

    ob = bpy.context.object
    set_collection(ob, info.collection)
    ob.name = info.name if info.name is not None else ob.name
    if info.parent_info:
        set_parent(ob, info.parent_info)
    set_material(ob, material_name)

    ob.data.uv_layers.new()

    return ob


def create_datablock_light(
    info: DatablockInfo,
    light_type: str,
    scene: Optional[Union[bpy.types.Scene, str]] = None,
):
    assert light_type in {"POINT", "SUN", "SPOT", "ARENA"}
    li = bpy.data.lights.new(info.name, light_type)
    ob = bpy.data.objects.new(info.name, li)
    set_collection(ob, info.collection)

    try:
        scene = bpy.data.scenes[scene]
    except (KeyError, TypeError):
        scene = bpy.context.scene
    set_collection(ob, info.collection)

    ob.location = info.location
    ob.rotation_mode = info.rotation_mode
    set_rotation(ob, info.rotation, info.rotation_mode)
    ob.scale = info.scale

    if info.parent_info:
        set_parent(ob, info.parent_info)

    return ob


def create_datablock_image_from_disk(filepath: Union[Path, str]) -> bpy.types.Image:
    """
    Create an image from a file on disk or re-uses it if possible.
    Returns bpy.types.Image or raises OSError
    """

    try:
        real_path = bpy.path.abspath(str(filepath))
        img = bpy.data.images.load(real_path, check_existing=True)
        return img
    except (RuntimeError, ValueError):  # Couldn't load or make relative path
        raise OSError(f"Cannot load image {real_path}")


def create_material(material_name: str):
    try:
        return bpy.data.materials[material_name]
    except:
        return bpy.data.materials.new(material_name)


def create_material_default() -> bpy.types.Material:
    """
    Creates the default 'Material' if it doesn't already exist
    """
    return create_material("Material")


def create_scene(name: str) -> bpy.types.Scene:
    try:
        return bpy.data.scenes[name]
    except KeyError:
        return bpy.data.scenes.new(name)


# Do not include .png. It is only for the source path
def get_image(name: str) -> Optional[bpy.types.Image]:
    """
    New images will be created in //tex and will be a .png
    """
    return bpy.data.images.get(name)


def get_light(name: str) -> Optional[bpy.types.Light]:
    """
    Gets, if possible, Light data, not the light object
    """
    return bpy.data.lights.get(name)


# Returns the bpy.types.Material or creates it as needed
def get_material(material_name: str) -> Optional[bpy.types.Material]:
    return bpy.data.materials.get(material_name)


def get_material_default() -> bpy.types.Material:
    mat = bpy.data.materials.get("Material")
    if mat:
        return mat
    else:
        return create_material_default()


def delete_all_collections():
    for coll in bpy.data.collections:
        bpy.data.collections.remove(coll)


def delete_all_images():
    for image in bpy.data.images:
        image.user_clear()
        bpy.data.images.remove(image, do_unlink=True)


def delete_all_lights():
    for light in bpy.data.lights:
        light.user_clear()
        bpy.data.lights.remove(light, do_unlink=True)


def delete_all_materials():
    for material in bpy.data.materials:
        material.user_clear()
        bpy.data.materials.remove(material, do_unlink=True)


def delete_all_objects():
    for obj in bpy.data.objects:
        obj.user_clear()
        bpy.data.objects.remove(obj, do_unlink=True)


def delete_all_other_scenes():
    """
    Note: We can't actually delete all the scenes since there has to be one
    """
    for scene in bpy.data.scenes[1:]:
        scene.user_clear()
        bpy.data.scenes.remove(scene, do_unlink=True)


def delete_all_text_files():
    for text in bpy.data.texts:
        text.user_clear()
        bpy.data.texts.remove(text, do_unlink=True)


def delete_everything():
    """
    Warning! Don't call this from a Blender script!
    You'll delete the text block you're using!
    """
    delete_all_images()
    delete_all_materials()
    delete_all_objects()
    delete_all_text_files()
    delete_all_collections()
    delete_all_other_scenes()


# The create_ and set_ helpers use each other. Imported last, once every create_ helper above exists
from .test_setting_helpers import *  # noqa: E402
