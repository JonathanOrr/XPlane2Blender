"""
Every object's and bone's location and rotation at every keyframe of the scene, read once per export.
"""

import collections
import dataclasses
from typing import Dict, Tuple, Union

import bpy
import mathutils

from io_xplane2blender import xplane_helpers


@dataclasses.dataclass(frozen=True)
class LocRotPerFrame:
    """Location/Rotation information at each frame we could care about, copied"""

    frame_num: int
    location: mathutils.Vector
    rotation_mode: str
    rotation: Union[
        mathutils.Euler, mathutils.Quaternion, Tuple[float, float, float, float]
    ]


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
            l = LocRotPerFrame(
                frame_num,
                obj.location.copy(),
                obj.rotation_mode,
                xplane_helpers.get_rotation_from_rotatable(obj),
            )
            scene_keyframe_infos[(obj.name, None)][frame_num] = l
        # --- End objects to visit ---------------
    # --- End frames to visit---------------------
    bpy.context.scene.frame_set(1)
    _all_keyframe_infos[bpy.context.scene.name] = scene_keyframe_infos
    return
