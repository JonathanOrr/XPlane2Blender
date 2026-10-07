"""
The matrices of an XPlaneBone: where it is before and after its animation, and what is baked into its
vertices and its children.
"""

import mathutils


class XPlaneBoneMatrices:
    """The matrix half of XPlaneBone"""

    def getBlenderWorldMatrix(self) -> mathutils.Matrix:
        if self.blenderBone:
            # Blender bones in their current pose (which matches the shape of all data
            # blocks 'right now') are stored as a transform in the pose bone relative
            # to the parent armature.  So it's easy to export them:
            poseBone = self.blenderObject.pose.bones[self.blenderBone.name]
            if poseBone:
                return self.blenderObject.matrix_world.copy() @ poseBone.matrix.copy()
            else:
                # FIXME: is there ever not a pose bone for a bone?  Should this be some kind of assert?
                return (
                    self.blenderObject.matrix_world.copy()
                    @ self.blenderBone.matrix_local.copy()
                )
        elif self.blenderObject:
            # Data blocks simply know their world-space location post-transform.
            return self.blenderObject.matrix_world.copy()
        # Root bone gets a special exception: if it has a None blender object, then we are parented to
        # the glboal coordinate system
        elif self.parent == None:
            return mathutils.Matrix.Identity(4)
        else:
            # Wat!?!  We have a non-root bone with NO blender stuff attached.
            raise Exception()

    #
    # THE PRE-ANIMATION MATRIX (POSE)
    #
    # This matrix represents the world space pose in the rest position of this bone _before_
    # its animations are applied.  This is the frame of reference in which the animations are
    # happening.
    #
    # It is only legal to ask for this if (1) a bone is animated and (2) it is not the root
    # bone.
    def getPreAnimationMatrix(self) -> mathutils.Matrix:
        if self.parent == None:
            # No one should ever need the pre-animation matrix of the root bone -
            # we only need this to get a bake matrix between two animations.
            print("Pre-animation requested on root bone - who requested this?")
            raise Exception()
        elif not self.isAnimated():
            # We should not ask for pre and post animation matrices when there is no
            # animation - if we did, the code has failed to optimize something out.
            print(self)
            raise Exception()
        elif self.blenderBone:

            poseBone = self.blenderObject.pose.bones[self.blenderBone.name]

            static_translation = mathutils.Matrix.Identity(4)
            if not self.isDataRefAnimatedForTranslation():
                static_translation = mathutils.Matrix.Translation(
                    poseBone.matrix_basis.to_translation()
                )

            if self.blenderBone.parent and poseBone and poseBone.parent:
                # This special cases a bone that is parented to another bone.  In this case, we have a
                # problem: Blender stores all bones relative to the armature, both in rest and in pose.
                # This doesn't give us access to the bone _after_ its parent's transform but _before_
                # it's own animation.
                #
                # So we construct it ourselves.  r2r is the _relative_ transform from the parent bone
                # to our bone when at rest - in other words, it's the bake matrix from our parent bone to us.
                r2r = (
                    self.blenderBone.parent.matrix_local.inverted_safe()
                    @ self.blenderBone.matrix_local
                )
                # Now we can formulate that the full transform is:
                # 1. Armature's world space
                # 2. Our parent's pose
                # 3. The bake matrix from our parent's pose to us.
                # This gets us up to right before our transform.
                return (
                    self.blenderObject.matrix_world.copy()
                    @ poseBone.parent.matrix.copy()
                    @ r2r
                ) @ static_translation

            # This is the unparented bone case (and any fall-throughs from crazy objects):
            # Simply apply our rest position (relative to the armature) to the armature's current world-space
            # position.
            return (
                self.blenderObject.matrix_world.copy()
                @ self.blenderBone.matrix_local.copy()
                @ static_translation
            )

        elif self.blenderObject:

            # Animated objects are affected by "a bunch of stuff" that Blender does - it's hard to predict what it all is.
            # But data block animation is the LAST thing that happens.  So we can basically take our post-animation pose,
            # back out the known animation, and that's our pre-animation pose.

            # (In previous versions we used to start with the parent and work forward, but this required simulating the
            # parent-child transformation, which involves a bunch of specal logic fo bones.
            # This is more reliable.

            # This is our final post-data block animation pose. (Technically it's MORE than post-animation if we have a dynamic
            # translation and static rotation, for example.)
            my_final = self.getBlenderWorldMatrix()

            # This is all of the transformations (rot,loc,scale) that our data block might do.
            my_block = self.blenderObject.matrix_basis

            # If we are NOT animated for translation and we are here we MUST be animated for rotation.  In this case, we want
            # to treat ONLY the rotation part as "dynamic" - so nuke the translation components.
            if not self.isDataRefAnimatedForTranslation():
                my_block = my_block.to_3x3().to_4x4()

            # This is the "undo" of the dynamic part of our block transform
            before_my_block = my_block.inverted_safe()

            # Final result is our post-animation pose with the dynamic animatons subtracted out.  This will nuke either
            # rotation or rotatio + location.
            return my_final @ before_my_block

    #
    # THE POST-ANIMATION MATRIX (POSE)
    #
    # This matrix represents the world space pose of the bone just after all dynamic animation.  EVERY
    # bone has this, because everything "on" the bone (sub-bones, meshes) is attached to this pose.
    #
    def getPostAnimationMatrix(self) -> mathutils.Matrix:
        if self.parent == None:
            # WARNING: If the root bone has been scaled then the scale does NOT apply to the OBJ.
            # This is probably technically correct based on some insane fine-print reading of export-by-object
            # but may astonish users.
            return (
                self.getBlenderWorldMatrix()
            )  # correctly returns Identity for root bone
        elif not self.isAnimated():
            # No one should be asking or post-animation matrices on _non_-animated bones!
            print(self)
            raise Exception()
        else:
            # Scaling trickery: we have to BACK OUT the scaling of our post-animation matrix...this
            # pushes it into the next bake, which means eventually the mesh vertices themselves get scaled.
            # If we DONT'T do this then scaling "above" an animation won't scale what's below because the code
            # assumes that the entire transform stack is "applied" in the OBJ file before we continue from an
            # animation - and since OBJs don't scale, we can't do that.  Obviously if something that is
            # impossible-in-OBJ happens, the pushed-through scaling will be wrong.
            #
            # Rotation trickery: if our rotation was static, we are goint to back that out of our post-animation too,
            # forcing it into the bake matrix.  This is correct and removes the need for static rotations.

            # First: get our world matrix without ANY scaling.
            world_matrix = self.getBlenderWorldMatrix()
            loc, rot, scale = world_matrix.decompose()
            world_matrix_no_scale = (
                mathutils.Matrix.Translation(loc) @ rot.to_matrix().to_4x4()
            )
            # If there is no scaling, just take our real matrix, don't decompose and recompose.  This aims to
            # avoid floating point crap accumulation
            if scale == mathutils.Vector((1.0, 1.0, 1.0)):
                world_matrix_no_scale = world_matrix

            if not self.isDataRefAnimatedForRotation():
                # No-rotation case: back out ONLY OUR rotation.  Note that our parents rotations and other random
                # rotations are kept in!

                if self.blenderBone:
                    poseBone = self.blenderObject.pose.bones[self.blenderBone.name]
                    our_loc, our_rot, our_scale = poseBone.matrix_basis.decompose()
                else:
                    (
                        our_loc,
                        our_rot,
                        our_scale,
                    ) = self.blenderObject.matrix_basis.decompose()

                our_rot_inv = our_rot.to_matrix().to_4x4().inverted_safe()
                return world_matrix_no_scale @ our_rot_inv
            else:
                return world_matrix_no_scale

    #
    # ANIMATION BAKE MATRIX (DELTA)
    #
    # A bake matrix is a _delta_ - a transformation from one pose to another that is static in the model, and therefore can
    # be implemented by "applying" the transform to the child things, instead of writing it as ANIM_ directives.
    # In other wods, it is a static relative transform that is elligible for 'baking'.
    #
    # Baking is important because without it, the exporter would have to output a ton of transform code for 'highly structured'
    # (but not dynamic) models; with baking, an author can use lots of sub-blocks and relative positioning and still just get
    # triangles.
    #
    # The bake matrix for animations for bone X is the static transform _from X's parent bone to X before its animations.
    # In other words, once we are in X's parent's coordinate system, we need to do this bake to then apply our animations.
    def getBakeMatrixForMyAnimations(self) -> mathutils.Matrix:
        parent_bone = self.getFirstAnimatedParent()
        if parent_bone == None:
            # If we have no parent bone, our bake matrix goes from global coordinates TO our pre-animation pose.
            # This would be more formal if it was inverse(identity) @ getPreAnimationMatrix() - this has been
            # simplifiied.
            return self.getPreAnimationMatrix()
        else:
            # This is the parent transform we are going from
            parent_post = self.getFirstAnimatedParent().getPostAnimationMatrix()
            # This is the child we are going to
            pre = self.getPreAnimationMatrix()
            return parent_post.inverted_safe() @ pre

    # ATTACHENT BAKE MATRIX (DELTA)
    #
    # This bake matrix is the delta from the final bone (post animation) to an actual THING like a mesh or a light.
    #
    # This API gets the bake matrix to be applied to output-able primitives that are attached to -this- bone.
    # In other words, this is a helper for how to bake our lights, meshes, etc.
    #
    def getBakeMatrixForAttached(self) -> mathutils.Matrix:
        # Our anchor bone is the thing we are attached to - it might be us, or it might be our parent.
        if self.isAnimated():
            my_anchor_bone = self  # The anchor bone is the last bone to be animated -
        else:  # We are 'in' its post-animation coordinate system
            my_anchor_bone = self.getFirstAnimatedParent()

        if my_anchor_bone == None:
            # If my anchor bone is _none_, it means that there is both no animation AND no parent
            # bone of ANY kind.  This happens when we do a by-object export and the user sets the
            # mesh data block ITSELF to be a root.  In this case, we are our own coordinate system,
            # so our bake is the identity.
            return mathutils.Matrix.Identity(4)
        else:
            anchor_post_anim = my_anchor_bone.getPostAnimationMatrix()
            my_final_world = self.getBlenderWorldMatrix()
            # Find the relative matrix from the post-animation of our last animated bone to our final post animation transform.
            return anchor_post_anim.inverted_safe() @ my_final_world
