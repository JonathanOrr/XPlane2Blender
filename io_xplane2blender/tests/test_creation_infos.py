"""The Info structs that describe what a test creates: datablocks, bones, keyframes, parents"""

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

# Constants
_ARMATURE = "ARMATURE"
_BONE = "BONE"
_OBJECT = "OBJECT"


class AxisDetentRangeInfo:
    def __init__(self, start: float, end: float, height: float):
        self.start = start
        self.end = end
        self.height = height


class BoneInfo:
    def __init__(self, name: str, head: Vector, tail: Vector, parent: str):
        assert len(head) == 3 and len(tail) == 3
        self.name = name
        self.head = head
        self.tail = tail

        def round_vec(vec):
            return Vector([round(comp, 5) for comp in vec])

        assert (round_vec(self.tail) - round_vec(self.head)) != Vector((0, 0, 0))
        self.parent = parent


class DatablockInfo:
    """
    The POD struct used for creating datablocks.
    If None is given as a parameter, sensible defaults are used:

    parent_info - When None no parent is assigned
    collection - When None, current scene's 'Master Collection' is used
    rotation - When None, the default for rotation_mode is used

    Values for datablock_type must be 'MESH', 'ARMATURE', 'EMPTY', or "LIGHT"
    """

    def __init__(
        self,
        datablock_type: str,
        name: str,
        parent_info: "ParentInfo" = None,
        collection: Optional[Union[str, bpy.types.Collection]] = None,
        location: Vector = Vector((0, 0, 0)),
        rotation_mode: str = "XYZ",
        rotation: Optional[Union[bpy.types.bpy_prop_array, Euler, Quaternion]] = None,
        scale: Vector = Vector((1, 1, 1)),
    ):
        self.datablock_type = datablock_type
        self.name = name
        if collection is None:
            self.collection = bpy.context.scene.collection
        else:
            from .test_creation_datablocks import create_datablock_collection

            self.collection = (
                collection
                if isinstance(collection, bpy.types.Collection)
                else create_datablock_collection(collection)
            )

        self.parent_info = parent_info
        self.location = location
        self.rotation_mode = rotation_mode
        if rotation is None:
            if self.rotation_mode == "AXIS_ANGLE":
                self.rotation = (0.0, Vector((0, 0, 0, 0)))
            elif self.rotation_mode == "QUATERNION":
                self.rotation = Quaternion()
            elif set(self.rotation_mode) == {"X", "Y", "Z"}:
                self.rotation = Vector()
            else:
                assert False, "Unsupported rotation mode: " + self.rotation_mode
        else:
            if self.rotation_mode == "AXIS_ANGLE":
                assert len(self.rotation[1]) == 3
                self.rotation_axis_angle = rotation
            elif self.rotation_mode == "QUATERNION":
                assert len(self.rotation) == 4
                self.rotation_quaternion = rotation
            elif set(self.rotation_mode) == {"x", "y", "z"}:
                assert len(self.rotation) == 3
                self.rotation_euler = rotation
            else:
                assert False, "Unsupported rotation mode: " + self.rotation_mode

            self.rotation = rotation
        self.scale = scale


class KeyframeInfo:
    def __init__(
        self,
        idx: int,
        dataref_path: str,
        dataref_value: Optional[float] = None,
        dataref_show_hide_v1: Optional[float] = None,
        dataref_show_hide_v2: Optional[float] = None,
        dataref_anim_type: str = xplane_constants.ANIM_TYPE_TRANSFORM,  # Must be xplane_constants.ANIM_TYPE_*
        location: Optional[Vector] = None,
        rotation_mode: str = "XYZ",
        rotation: Optional[Union[Tuple[float, Vector], Euler, Quaternion]] = None,
    ):
        self.idx = idx
        self.dataref_path = dataref_path
        self.dataref_value = dataref_value
        self.dataref_show_hide_v1 = dataref_show_hide_v1
        self.dataref_show_hide_v2 = dataref_show_hide_v2
        self.dataref_anim_type = dataref_anim_type
        self.location = location
        self.rotation_mode = rotation_mode
        self.rotation = rotation

        if self.rotation:
            if self.rotation_mode == "AXIS_ANGLE":
                assert len(self.rotation[1]) == 3
            elif self.rotation_mode == "QUATERNION":
                assert len(self.rotation) == 4
            elif {*self.rotation_mode} == {"X", "Y", "Z"}:
                assert len(self.rotation) == 3
            else:
                assert False, "Unsupported rotation mode: " + self.rotation_mode

    def __str__(self) -> str:
        return f"({self.idx}, {self.dataref_path}, {self.dataref_value}, {self.dataref_show_hide_v1}, {self.dataref_show_hide_v2}, {self.dataref_anim_type}, {self.location}, {self.rotation_mode}, {self.rotation})"


# Common presets for animations
R_2_FRAMES_45_Y_AXIS = (
    KeyframeInfo(
        idx=1,
        dataref_path="sim/cockpit2/engine/actuators/throttle_ratio_all",
        dataref_value=0.0,
        rotation=(0, 0, 0),
    ),
    KeyframeInfo(
        idx=2,
        dataref_path="sim/cockpit2/engine/actuators/throttle_ratio_all",
        dataref_value=1.0,
        rotation=(0, 45, 0),
    ),
)

T_2_FRAMES_1_X = (
    KeyframeInfo(
        idx=1,
        dataref_path="sim/graphics/animation/sin_wave_2",
        dataref_value=0.0,
        location=(0, 0, 0),
    ),
    KeyframeInfo(
        idx=2,
        dataref_path="sim/graphics/animation/sin_wave_2",
        dataref_value=1.0,
        location=(1, 0, 0),
    ),
)

T_2_FRAMES_1_Y = (
    KeyframeInfo(
        idx=1,
        dataref_path="sim/graphics/animation/sin_wave_2",
        dataref_value=0.0,
        location=(0, 0, 0),
    ),
    KeyframeInfo(
        idx=2,
        dataref_path="sim/graphics/animation/sin_wave_2",
        dataref_value=1.0,
        location=(0, 1, 0),
    ),
)

SHOW_ANIM_S = (
    KeyframeInfo(
        idx=1,
        dataref_path="show_hide_dataref_show",
        dataref_show_hide_v1=0.0,
        dataref_show_hide_v2=100.0,
        dataref_anim_type=xplane_constants.ANIM_TYPE_SHOW,
    ),
)

SHOW_ANIM_H = (
    KeyframeInfo(
        idx=1,
        dataref_path="show_hide_dataref_hide",
        dataref_show_hide_v1=100.0,
        dataref_show_hide_v2=200.0,
        dataref_anim_type=xplane_constants.ANIM_TYPE_HIDE,
    ),
)

SHOW_ANIM_FAKE_T = (
    KeyframeInfo(idx=1, dataref_path="none", dataref_value=0.0, location=(0, 0, 0)),
    KeyframeInfo(idx=2, dataref_path="none", dataref_value=1.0, location=(0, 0, 0)),
)


class ParentInfo:
    def __init__(
        self,
        parent: Optional[bpy.types.Object] = None,
        parent_type: str = _OBJECT,  # Must be "ARMATURE", "BONE", or "OBJECT"
        parent_bone: Optional[str] = None,
    ):
        assert (
            parent_type == _ARMATURE or parent_type == _BONE or parent_type == _OBJECT
        )
        if parent:
            assert isinstance(parent, bpy.types.Object)

        if parent_bone:
            assert isinstance(parent_bone, str)
        self.parent = parent
        self.parent_type = parent_type
        self.parent_bone = parent_bone
