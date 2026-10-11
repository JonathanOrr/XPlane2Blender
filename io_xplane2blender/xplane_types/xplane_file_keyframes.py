"""
Every object's and bone's location and rotation at every keyframe of the scene, read once per export. An object's
location includes its delta location, and its delta rotation is settled by xplane_delta_transforms.
"""

import collections
import dataclasses
from typing import Dict, Optional, Tuple, Union

import bpy
import mathutils

from io_xplane2blender import xplane_helpers
from io_xplane2blender.xplane_types import xplane_delta_transforms as deltas


@dataclasses.dataclass(frozen=True)
class LocRotPerFrame:
    """Location/Rotation information at each frame we could care about, copied"""

    frame_num: int
    location: mathutils.Vector
    rotation_mode: str
    rotation: Union[
        mathutils.Euler, mathutils.Quaternion, Tuple[float, float, float, float]
    ]
    # The delta rotation, None when there is none, and where it went once settled
    delta: Optional[Union[mathutils.Euler, mathutils.Quaternion]] = None
    delta_case: str = deltas.NONE


ObjectBoneNameKey = Tuple[str, str]
FrameToLocRotPerFrame = Dict[int, LocRotPerFrame]


# IMPORTANT! You must clear this cache when finished exporting all your OBJs,
# or you'll never export new animations! We clear in
# - xplane_file.createFilesFromBlenderRootObjects - from using the export operator
# - tests/__init__.exportExportableRoot - from using a test
_all_keyframe_infos: Dict[str, Dict[ObjectBoneNameKey, FrameToLocRotPerFrame]] = (
    collections.defaultdict(dict)
)


def _pre_scan_all_keyframes():
    """Returns a copy of all this scene's LocRotPerFrame, scanning for it as needed"""

    ###--- THIS IS A HOTPATH -------------------------------------------------
    # Do not change without profiling
    #
    # Calling frame_set __once__ per every keyframe in a scene is
    # a huge performance win. We cache the results in case the user has multiple roots
    # in a scene

    global _all_keyframe_infos
    if bpy.context.scene.name in _all_keyframe_infos:
        return
    else:
        scene_keyframe_infos = collections.defaultdict(dict)

    # A set of all keyframes that could have data we care about
    frames_to_visit = sorted(
        {
            int(kf.co[0])
            for fcurve in xplane_helpers.get_all_actions_fcurves()
            for kf in fcurve.keyframe_points
            if kf.co[0].is_integer()
        }
    )

    # --- Begin frames to visit-------------------
    for frame_num in frames_to_visit:
        bpy.context.scene.frame_set(frame_num)

        # --- Begin objects to visit -------------
        for obj in bpy.context.scene.objects:
            if obj.type == "ARMATURE":
                # --- Begin bones to visit -------
                for bone in obj.pose.bones:
                    l = LocRotPerFrame(
                        frame_num,
                        bone.location.copy(),
                        bone.rotation_mode,
                        xplane_helpers.get_rotation_from_rotatable(bone),
                    )

                    scene_keyframe_infos[(obj.name, bone.name)][frame_num] = l
                # --- End bones to visit ---------
            scene_keyframe_infos[(obj.name, None)][frame_num] = object_info(obj, frame_num)
        # --- End objects to visit ---------------
    # --- End frames to visit---------------------
    for (_, bone_name), frames in scene_keyframe_infos.items():
        if bone_name is None:
            deltas.settle(frames)
    bpy.context.scene.frame_set(1)
    _all_keyframe_infos[bpy.context.scene.name] = scene_keyframe_infos
    return


def object_info(obj: bpy.types.Object, frame_num: int) -> LocRotPerFrame:
    """The object's location (with its delta location) and rotations now. Settle a frame on its own"""
    return LocRotPerFrame(
        frame_num,
        obj.location + obj.delta_location,
        obj.rotation_mode,
        xplane_helpers.get_rotation_from_rotatable(obj),
        deltas.delta_rotation(obj),
    )


def delta_case(obj: bpy.types.Object) -> str:
    """Where the object's delta rotation went in the keyframes read for this export (see xplane_delta_transforms)"""
    frames = _all_keyframe_infos.get(bpy.context.scene.name, {}).get((obj.name, None))
    if frames:
        return next(iter(frames.values())).delta_case
    return deltas.NONE if deltas.delta_rotation(obj) is None else deltas.STATIC
