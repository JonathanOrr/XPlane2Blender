"""
About the XPlaneBone/XPlaneObject API
=====================================
XPlane2Blender makes it's own hierarchy of Blender objects,
which under most circumstances looks nearly identical
to the Blender hierarchy in the outliner.

However, where as the Blender Outliner is focused on Collections and Objects and the parent-child
connections between them, the XPlane2Blender hierarchy is focused on a tree
structure of XPlaneBones with XPlaneObjects optionally associated with them.

XPlane2Blender primarily uses this tree to make animations

Rules:
- XPlaneBones are made for the Root Collection and every Object and Armature Bone encountered
- XPlaneBones will not have an XPlaneObject if the Blender Object is unconvertible (such as the root collection, camera, and sound emitters)
- Every XPlaneBone (except the Root Bone under collections) must have a Blender Object associated with it
- Every Blender Object appears in the XPlaneBone Tree exactly once

Special Collection Rules:
- The root bone will have no Blender Object or XPlaneObject associated with it

Because XPlaneBones represent different relationships than Blender's parent-child
relationships, it cannot be assumed that the XPlaneBone Tree and Blender Hierarchy are the same.

**Therefore, all APIs should use the XPlaneBone tree's version of parent and child lookups instead of the Blender's!**
"""

from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

import bpy

from io_xplane2blender import xplane_props
from io_xplane2blender.xplane_config import getDebug
from io_xplane2blender.xplane_helpers import (
    get_action_fcurves,
    is_multiplayer_dataref,
    logger,
)
from io_xplane2blender.xplane_types.xplane_keyframe import XPlaneKeyframe
from io_xplane2blender.xplane_types.xplane_keyframe_collection import (
    XPlaneKeyframeCollection,
)

from .xplane_bone_matrices import XPlaneBoneMatrices
from .xplane_bone_writer import XPlaneBoneWriter

if TYPE_CHECKING:
    from io_xplane2blender.xplane_types.xplane_file import XPlaneFile
    from io_xplane2blender.xplane_types.xplane_object import XPlaneObject


class XPlaneBone(XPlaneBoneMatrices, XPlaneBoneWriter):
    def __init__(
        self,
        xplane_file: "XPlaneFile",
        blender_obj: Optional[bpy.types.Object],
        blender_bone: Optional[bpy.types.Bone] = None,
        xplane_obj: Optional["XPlaneObject"] = None,
        parent_xplane_bone: Optional["XPlaneBone"] = None,
    ):
        """
        self.blenderObject is the Blender Object associated with this XPlaneBone (according to our traversal of the Blender hierarchy).
        It is only None for the root XPlaneBone of an Exportable Collection

        self.blenderBone is the Blender Bone associated with this XPlaneBone (if the origin during traversal was a bpy.types.Bone)
        Thus, you can tell if something was a Bone by if blenderBone is not None

        XPlaneBone is responsible for tieing the xplane_obj (if any) with this XPlaneBone, and adding
        the us to the parent_xplane_bone's children. This way it is all kept in one place and can't be forgotten
        """
        self.xplaneFile = xplane_file
        self.blenderObject = blender_obj
        self.blenderBone = blender_bone
        self.xplaneObject = xplane_obj
        self.parent = parent_xplane_bone
        self.children: List["XPlaneBone"] = []

        if self.xplaneObject:
            assert (
                self.xplaneObject.blenderObject == self.blenderObject
            ), f"XPlaneBone ({self.blenderObject.name}) and XPlaneObject's blenderObject do not match ({self.blenderObject.name}, {self.xplaneObject.name})"
            self.xplaneObject.xplaneBone = self
            if self.xplaneObject.blenderObject.xplane.override_lods:
                self.xplaneObject.effective_buckets = tuple(
                    self.blenderObject.xplane.lod
                )
            else:

                def find_parent_buckets(
                    parent_xplane_bone: Optional["XPlaneBone"],
                ) -> Tuple[bool, bool, bool, bool]:
                    try:
                        if parent_xplane_bone.xplaneObject:
                            return parent_xplane_bone.xplaneObject.effective_buckets
                        elif parent_xplane_bone.parent:
                            return find_parent_buckets(parent_xplane_bone.parent)
                        else:
                            return (False,) * 4
                    except AttributeError:
                        return (False,) * 4

                self.xplaneObject.effective_buckets = find_parent_buckets(self.parent)

        if self.parent:
            self.parent.children.append(self)

        # dict - The keys are the dataref paths and the values are lists of <XPlaneKeyframeCollection>.
        self.animations = (
            {}
        )  # type: Dict[bpy.types.StringProperty,XPlaneKeyframeCollection]

        # IMPORTANT NOTE: Show/Hide Datarefs and datarefs without 2 keyframes will not be included and
        # must be accessed via blenderObject.xplane.datarefs!
        self.datarefs: Dict[str, xplane_props.XPlaneDataref] = {}
        self.collectAnimations()

    def sortChildren(self) -> None:
        def getWeight(xplaneBone) -> int:
            if xplaneBone.xplaneObject:
                return xplaneBone.xplaneObject.weight

            return 0

        self.children.sort(key=getWeight)

    # Method: isAnimatedForTranslation
    # Checks if a dataref's keyframes actually contain meaningful translations, and we should therefore write keyframes out
    def isDataRefAnimatedForTranslation(self) -> bool:
        if hasattr(self, "animations") and len(self.animations) > 0:
            # Check to see if there is at least some difference in the keyframe locations
            for dataref in self.animations:
                keyframes = self.animations[dataref]
                if len(keyframes) > 0:
                    last_keyframe = keyframes[0]
                    for keyframe in keyframes:
                        # if there is a difference
                        if keyframe.location != last_keyframe.location:
                            return True
                        else:
                            last_keyframe = keyframe

        return False

    # Method: isAnimatedForRotation
    # Checks if a dataref's keyframes actually contain meaningful rotation, and we should therefore write keyframes out
    def isDataRefAnimatedForRotation(self) -> bool:
        if hasattr(self, "animations") and len(self.animations) > 0:
            # Check to see if there is at least some difference in the keyframe locations
            for dataref in self.animations:
                keyframes = self.animations[dataref]
                if len(keyframes) > 0:
                    last_keyframe = keyframes[0]
                    for keyframe in keyframes:
                        # if there is a difference
                        if keyframe.rotation != last_keyframe.rotation:
                            return True
                        else:
                            last_keyframe = keyframe

        return False

    def isAnimated(self) -> bool:
        """Uses isDataRefAnimated functions to check if the object is animated"""
        return (
            self.isDataRefAnimatedForTranslation()
            or self.isDataRefAnimatedForRotation()
        )

    def collectAnimations(self) -> None:
        """
        Collects animation_data from blenderObject, and pairs it with xplane datarefs
        """
        if not self.parent:
            return None

        debug = getDebug()

        bone = self.blenderBone
        blenderObject = self.blenderObject

        # check for animation
        # if bone:
        # print("\t\t checking animations of %s:%s" % (blenderObject.name, bone.name))
        # else:
        # print("\t\t checking animations of %s" % blenderObject.name)

        if bone:
            # bone animation data resides in the armature objects .data block
            fcurves = [
                f
                for f in get_action_fcurves(blenderObject.data)
                if f.data_path.startswith(f'bones["{bone.name}"].xplane.datarefs')
            ]
        else:
            fcurves = [
                f
                for f in get_action_fcurves(blenderObject)
                if f.data_path.startswith(f"xplane.datarefs")
            ]

        for fcurve in fcurves:
            if bone:
                index = int(
                    fcurve.data_path[
                        len(f'bones["{bone.name}"].xplane.datarefs[') : -len("].value")
                    ]
                )
            else:
                index = int(fcurve.data_path[len("xplane.datarefs[") : -len("].value")])

            try:
                if bone:
                    dataref = bone.xplane.datarefs[index].path
                else:
                    dataref = blenderObject.xplane.datarefs[index].path
            except IndexError:
                # Due to a long standing bug in (I think in BONE_OT_remove_xplane_dataref.execute)
                # sometimes a Bone's fcurve is not properly removed. Any further indexes will also
                # be wrong.
                #
                # TODO: Fix whatever is causing this, but, we'll still need this for old .blend files
                # - Ted, 6/24/2020
                return
            else:
                if len(fcurve.keyframe_points) > 1:
                    if bone:
                        self.datarefs[dataref] = bone.xplane.datarefs[index]
                    else:
                        self.datarefs[dataref] = blenderObject.xplane.datarefs[index]

                    self.animations[dataref] = XPlaneKeyframeCollection(
                        [
                            XPlaneKeyframe(kf, i, dataref, self)
                            for i, kf in enumerate(fcurve.keyframe_points)
                        ]
                    )

                    if is_multiplayer_dataref(dataref):
                        logger.error(
                            "'{}' uses the multiplayer dataref '{}', which must not be used in objects. Choose another dataref.".format(
                                bone.name if bone else blenderObject.name, dataref
                            )
                        )

    def getName(self, ignore_indent_level: bool = False) -> str:
        """
        Gets the (optionally) indent level, Blender Type, and name.
        Useful for debugging and error message.

        Note: Unit tests, like the ones in xplane_file,
        test against the output of this method!
        """
        count_parents = lambda bone: (
            1 + count_parents(bone.parent) if bone.parent else 0
        )
        prefix = "" if ignore_indent_level else f"{count_parents(self)} "

        if self.blenderBone:
            return f"{prefix}Bone: {self.blenderBone.name}"
        elif self.blenderObject:
            return (
                f"{prefix}{self.blenderObject.type.title()}: {self.blenderObject.name}"
            )
        elif self.parent == None:
            return f"{prefix}ROOT"
        else:
            assert (
                False
            ), "XPlaneBone has no Blender Data, but also is not the root. How did we did we get here?"

    def getBlenderName(self) -> str:
        if self.blenderBone:
            return self.blenderBone.name
        elif self.blenderObject:
            return self.blenderObject.name
        else:
            assert False, "Cannot call getBlenderName on a root bone"

    def getIndent(self) -> str:
        count_parents = lambda bone: (
            1 + count_parents(bone.parent) if bone.parent else 0
        )
        return "\t" * count_parents(self)

    def getFirstAnimatedParent(self) -> Optional[str]:
        if self.parent == None:
            return None

        if self.parent.isAnimated() or self.parent.parent == None:
            return self.parent
        else:
            return self.parent.getFirstAnimatedParent()

    # Blender World Matrix (Pose)
    #
    # This is the absolute final pose of a blender object after _everything_ is taken into account.
    # If we want to emit a mesh, this is where the mesh lives.  The world matrix might be "more"
    # transforms than post-animation if there is a static rotation after a dynamic translation.
    #

    def __str__(self) -> str:
        def toString(bone: "XPlaneBone", indent: str = "") -> str:
            out = indent + bone.getName() + "\n"

            for bone in bone.children:
                out += toString(bone, indent + "\t")

            return out

        out = toString(self)
        return out
