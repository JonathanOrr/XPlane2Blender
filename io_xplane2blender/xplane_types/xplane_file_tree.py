"""
Builds an XPlaneFile's tree of XPlaneBones from the Blender hierarchy below its root.
"""

from typing import Dict, List, Optional, Union

import bpy

from io_xplane2blender.xplane_types import (
    xplane_empty,
)

from ..xplane_helpers import (
    ExportableRoot,
    logger,
)
from .xplane_bone import XPlaneBone
from .xplane_light import XPlaneLight
from .xplane_object import XPlaneObject
from .xplane_primitive import XPlanePrimitive


class XPlaneFileTree:
    """The tree building half of XPlaneFile"""

    def create_xplane_bone_hiearchy(
        self, exportable_root: ExportableRoot
    ) -> Optional[XPlaneObject]:
        def allowed_children(
            parent_like: Union[bpy.types.Collection, bpy.types.Object],
        ) -> List[bpy.types.Object]:
            """
            Returns only the objects the recurse function is allowed to use.
            If a problematic object is found, errors and warnings may be
            emitted
            """
            # bones also have a .children attribute
            assert isinstance(
                parent_like, (bpy.types.Collection, bpy.types.Object)
            ), "Only Collections and Objects are allowed"
            try:
                children = sorted(parent_like.all_objects, key=lambda r: r.name)
            except AttributeError:
                children = parent_like.children

            allowed_children = []
            for child_obj in children:
                if child_obj.name not in bpy.context.scene.objects:
                    logger.warn(
                        f"{child_obj.name} is outside the current scene. It and any children cannot be collected"
                    )
                else:
                    allowed_children.append(child_obj)
            return allowed_children

        def convert_to_xplane_object(
            blender_obj: bpy.types.Object,
        ) -> Optional[XPlaneObject]:
            assert (
                blender_obj
            ), "blender_obj in convert_to_xplane_object must not be None"
            converted_xplane_obj = None
            if blender_obj.type == "MESH":
                converted_xplane_obj = XPlanePrimitive(blender_obj)
            elif blender_obj.type == "LIGHT":
                converted_xplane_obj = XPlaneLight(blender_obj)
            elif blender_obj.type == "ARMATURE":
                converted_xplane_obj = XPlaneObject(blender_obj)
            elif blender_obj.type == "EMPTY":
                converted_xplane_obj = xplane_empty.XPlaneEmpty(blender_obj)

            return converted_xplane_obj

        def walk_upward(walk_start_bone: XPlaneBone):
            """
            Re-oganizes the XPlaneBone tree to include
            a Blender Object's out of collection parents
            """
            assert (
                walk_start_bone.blenderObject.parent
            ), "Walk up must have at least one parent to travel to"

            new_bones: List[XPlaneBone] = []

            def walk_upward_recursive(current_bone: XPlaneBone) -> XPlaneBone:
                """
                Recurse up by parent until you find a reuse opportutiny
                or nothing. Returns the top of the branch which must be
                reconnected
                """
                # If we haven't reached the top yet, make a bone for parent and move the head
                blender_obj = current_bone.blenderObject
                parent_obj = blender_obj.parent
                # --- Check for a reuse opportunity ------------------------
                if parent_obj and parent_obj.name in self._bl_obj_name_to_bone:
                    return current_bone
                elif parent_obj:
                    # ---------------------------------------------------------
                    # This is all the manual work
                    # the __init__ of XPlaneBone and XPlaneObject, and _recurse normally does for us
                    # - Converting parent_obj to an XPlaneObject (if possible)
                    # - Setting export_animation_only to True if outside collection,
                    #   or if we're re-entering, setting based on visible_get
                    # - Creating an XPlaneBone, and attaching the current bone as the new bone's child*
                    # - Running the new_parent's collect
                    # - Running walk_up to find it's split parents
                    # *Okay, this isn't a part of _recurse, but, I thought I should mention it while on
                    # the subject
                    # ----------------------------------------------------------
                    new_parent_xplane_obj = convert_to_xplane_object(parent_obj)
                    if new_parent_xplane_obj:
                        if (
                            not new_parent_xplane_obj.blenderObject.name
                            in exportable_root.all_objects
                        ):
                            # We don't have to test for blender_obj.visible_get here,
                            # all objects that start inside the exportable collection will
                            # have the assumption of being False - XPlaneObject's default for this is False
                            new_parent_xplane_obj.export_animation_only = True
                        else:
                            new_parent_xplane_obj.export_animation_only = (
                                not new_parent_xplane_obj.blenderObject.visible_get()
                            )

                    try:
                        if (
                            parent_obj.type == "ARMATURE"
                            and blender_obj.parent_type == "BONE"
                        ):
                            parent_bl_bone = parent_obj.data.bones[
                                blender_obj.parent_bone
                            ]
                        else:
                            parent_bl_bone = None
                    except KeyError as e:
                        parent_bl_bone = None

                    new_parent_bone = XPlaneBone(
                        xplane_file=self,
                        blender_obj=parent_obj,
                        # TODO: What if the parent is a nested bone? (bug #501)
                        blender_bone=parent_bl_bone,
                        xplane_obj=new_parent_xplane_obj,
                        parent_xplane_bone=None,
                    )

                    new_bones.append(new_parent_bone)
                    if new_parent_xplane_obj:
                        new_parent_xplane_obj.collect()
                    new_parent_bone.children.append(current_bone)
                    current_bone.parent = new_parent_bone
                    return walk_upward_recursive(new_parent_bone)
                else:
                    return current_bone

            top_of_branch = walk_upward_recursive(walk_start_bone)
            # 2 Types of reconnection
            # - Type A
            #   New branch needs re-connection to the root
            # - Type B
            #   Re-use of a previously walked to Blender Object out of collection
            if not top_of_branch.blenderObject.parent:
                reconnect_bone = self.rootBone
            else:
                reconnect_bone = self._bl_obj_name_to_bone[
                    top_of_branch.blenderObject.parent.name
                ]

            self.rootBone.children.remove(walk_start_bone)
            reconnect_bone.children.append(top_of_branch)
            top_of_branch.parent = reconnect_bone

            # This time we will have a parent!
            [bone.collectAnimations() for bone in new_bones]
            self._bl_obj_name_to_bone.update(
                {bone.blenderObject.name: bone for bone in new_bones}
            )

        def recurse(
            parent: Optional[bpy.types.Object],
            parent_bone: Optional[XPlaneBone],
            parent_blender_objects: bpy.types.Object,
        ) -> None:
            """
            Main function for recursing down tree.

            When parent is None
            - recurse is dealing with the first call of an exportable collection
            - parent_blender_objects = filtered coll.all_objects

            parent_blender_objects should always be filtered by allowed_children
            """
            # print(
            #   f"Parent: {parent.name}" if parent else f"Root: {exportable_root.name}",
            #   f"Parent Bone: {parent_bone}" if parent_bone else "No Parent Bone",
            #   f"parent_blender_objects {[o.name for o in parent_blender_objects]}",
            #   sep="\n"
            # )
            # print("===========================================================")

            blender_obj = parent

            try:
                self._bl_obj_name_to_bone[blender_obj.name]
            except (AttributeError, KeyError):
                found_blender_obj_already = False
            else:
                found_blender_obj_already = True

            def get_new_xplane_obj() -> Optional[XPlaneObject]:
                """
                When we're re-using a bone for various reasons,
                we call it a "new bone" and call it's object
                a "new object" so the rest of the algorithm doesn't get
                complicated
                """
                if found_blender_obj_already:
                    return self._bl_obj_name_to_bone[blender_obj.name].xplaneObject
                elif blender_obj:
                    return convert_to_xplane_object(blender_obj)
                else:
                    return None

            new_xplane_obj = get_new_xplane_obj()
            # print(f"new_xplane_obj:\n{new_xplane_obj}")

            is_root_bone = not parent_bone  # True for Exportable Collection and Object

            def get_new_xplane_bone() -> XPlaneBone:
                """
                If a non-root XPlaneBone is created
                it is auto added to the dict of existing bones.

                If we're re-using a bone we call it the "new" one,
                for the rest of the algorithm's sake
                """
                if found_blender_obj_already:
                    return self._bl_obj_name_to_bone[blender_obj.name]
                # We'll never have found the root bone already, you find it once
                elif is_root_bone and isinstance(exportable_root, bpy.types.Collection):
                    return XPlaneBone(self, blender_obj=None)
                elif not found_blender_obj_already:
                    new_xplane_bone = XPlaneBone(
                        xplane_file=self,
                        blender_obj=blender_obj,
                        blender_bone=None,
                        xplane_obj=new_xplane_obj,
                        parent_xplane_bone=parent_bone,
                    )
                    self._bl_obj_name_to_bone[blender_obj.name] = new_xplane_bone
                    return new_xplane_bone

            new_xplane_bone = get_new_xplane_bone()
            if is_root_bone:
                assert (
                    not self.rootBone
                ), "recurse should never be assigning self.rootBone twice"
                self.rootBone = new_xplane_bone
            try:
                if (
                    not found_blender_obj_already
                    and blender_obj.parent.name not in exportable_root.all_objects
                ):
                    if blender_obj.parent.name in bpy.context.scene.objects:
                        walk_upward(new_xplane_bone)
                    else:
                        logger.warn(
                            f"'{blender_obj.name}' parent is not in the same collection and is in a different scene. "
                            f"'{blender_obj.parent.name}' and any it's parents will not be searched for split animations"
                        )
            except AttributeError:  # For whatever of many reasons, we didn't walk up
                pass

            # We only collect once
            if not found_blender_obj_already and new_xplane_obj:
                # If set from walking up, keep that. Otherwise, decide based on visiblity
                new_xplane_obj.export_animation_only = (
                    new_xplane_obj.export_animation_only
                    or not blender_obj.visible_get()
                )
                new_xplane_obj.collect()
            elif not found_blender_obj_already and blender_obj:
                print(f"Blender Object: {blender_obj.name}, didn't convert")

            def make_bones_for_armature_bones(
                arm_obj: bpy.types.Object,
            ) -> Dict[str, XPlaneBone]:
                """
                Makes XPlaneBones for all bones in an armature, returns a map between
                Blender Bone Names and the XPlaneBones that are associated with them.

                These are used later to pair XPlaneObjects with their correct parent bones
                """
                assert arm_obj.type == "ARMATURE", arm_obj.name + " must be armature"
                blender_bones_to_xplane_bones = {}

                def _recurse_bone(bl_bone: bpy.types.Bone, parent_xp_bone: XPlaneBone):
                    """
                    Recurses down an armature's bone tree, making XPlaneBones for each Blender Bone
                    """
                    # For every 'Bone' we make an XPlaneBone all to itself, it becomes the new parent instead of the
                    # bone the armature is connected to
                    parent_xp_bone = XPlaneBone(
                        xplane_file=self,
                        blender_obj=arm_obj,
                        blender_bone=bl_bone,
                        xplane_obj=None,
                        parent_xplane_bone=parent_xp_bone,
                    )
                    blender_bones_to_xplane_bones[bl_bone.name] = parent_xp_bone
                    for child in bl_bone.children:
                        _recurse_bone(child, parent_xp_bone)

                # Run recurse for the top level bones
                for top_level_bone in filter(
                    lambda b: not b.parent, arm_obj.data.bones
                ):
                    _recurse_bone(top_level_bone, new_xplane_bone)
                return blender_bones_to_xplane_bones

            # If this is an armature, first build up the bones by tracking recursively down, then continue on
            # but skipping making the conversion again
            if blender_obj and blender_obj.type == "ARMATURE":
                real_bone_parents = make_bones_for_armature_bones(blender_obj)

            for child_obj in parent_blender_objects:
                if (
                    isinstance(exportable_root, bpy.types.Collection)
                    and child_obj.name not in exportable_root.all_objects
                ):
                    continue
                if (
                    blender_obj
                    and blender_obj.type == "ARMATURE"
                    and child_obj.parent_type == "BONE"
                ):
                    if child_obj.parent_bone not in blender_obj.data.bones:
                        logger.warn(
                            "".join(
                                (
                                    f"{child_obj.name}",
                                    " and its children" if child_obj.children else "",
                                    " will not export,",
                                    f" it's parent bone '{child_obj.parent_bone}' is",
                                    (
                                        f" not a real bone in {blender_obj.name}"
                                        if child_obj.parent_bone
                                        else " empty"
                                    ),
                                )
                            )
                        )
                        # Ignored cases don't get their children examined
                        continue
                    else:
                        parent_bone = real_bone_parents[child_obj.parent_bone]
                        assert (
                            parent_bone
                        ), "Must have parent bone for further recursion"
                        recurse(child_obj, parent_bone, allowed_children(child_obj))
                else:  # no parent by armature-bone
                    parent_bone = new_xplane_bone
                    recurse(child_obj, parent_bone, allowed_children(child_obj))
            try:
                if new_xplane_bone.blenderObject.type == "ARMATURE":
                    for xp_bone in real_bone_parents.values():
                        xp_bone.sortChildren()
            except AttributeError:  # Collection won't have a blenderObject
                pass
            new_xplane_bone.sortChildren()

        # --- end _recurse function -------------------------------------------
        if isinstance(exportable_root, bpy.types.Collection):
            all_allowed_objects = allowed_children(exportable_root)
            all_allowed_names = [o.name for o in all_allowed_objects]
            recurse(
                parent=None,
                parent_bone=None,
                parent_blender_objects=[
                    o
                    for o in all_allowed_objects
                    if o.parent is None or o.parent.name not in all_allowed_names
                ],
            )
        elif isinstance(exportable_root, bpy.types.Object):
            recurse(
                parent=exportable_root,
                parent_bone=None,
                parent_blender_objects=allowed_children(exportable_root),
            )
        else:
            assert False, f"Unsupported root_object type {type(exportable_root)}"

    def get_xplane_objects(self) -> List["XPlaneObject"]:
        """
        Returns a list of all XPlaneObjects collected by recursing down the
        completed XPlaneBone tree
        """
        assert self.rootBone, "Must be called after collection is finished"

        def get_xplane_objects_from_bone_tree(
            bone: XPlaneBone,
        ) -> List["XPlaneObject"]:
            xp_objects = []
            if bone.xplaneObject:
                xp_objects.append(bone.xplaneObject)
            for child_bone in bone.children:
                xp_objects.extend(get_xplane_objects_from_bone_tree(child_bone))
            return xp_objects

        return get_xplane_objects_from_bone_tree(self.rootBone)
