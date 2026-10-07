"""
Writes an XPlaneBone's animation: ANIM_begin, static moves and turns, keyframe tables, show/hide and ANIM_end.
"""

import math

import mathutils

from io_xplane2blender import xplane_constants
from io_xplane2blender.xplane_config import getDebug
from io_xplane2blender.xplane_helpers import (
    floatToStr,
    vec_b_to_x,
)
from io_xplane2blender.xplane_types.xplane_keyframe_collection import (
    XPlaneKeyframeCollection,
)


class XPlaneBoneWriter:
    """The writing half of XPlaneBone"""

    def writeAnimationPrefix(self) -> None:
        debug = getDebug()
        indent = self.getIndent()
        o = ""

        if debug:
            o += indent + "# " + self.getName() + "\n"
            """
            if self.blenderBone:
                poseBone = self.blenderObject.pose.bones[self.blenderBone.name]
                if poseBone != None:
                    o += "# Armature\n" + str(self.blenderObject.matrix_world) + "\n"
                    if self.blenderBone.parent:
                        poseParent = self.blenderObject.pose.bones[self.blenderBone.parent.name]
                        if poseParent:
                            o += "#  parent matrix local rest\n" + str(self.blenderBone.parent.matrix_local) + "\n"
                            o += "#  parent matrix local pose\n" + str(poseParent.matrix) + "\n"
                            o += "#  delta r2r\n" + str(self.blenderBone.parent.matrix_local.inverted_safe() @ self.blenderBone.matrix_local) + "\n"
                            o += "#  delta p2p\n" + str(poseParent.matrix.inverted_safe() @ poseBone.matrix) + "\n"
                    o += "#   matrix local rest\n" + str(self.blenderBone.matrix_local) + "\n"
                    o += "#   matrix local pose\n" + str(poseBone.matrix) + "\n"
                    o += "#   pose delta\n" + str(self.blenderBone.matrix_local.inverted_safe() @ poseBone.matrix) + "\n"
            elif self.blenderObject != None:
                o += "# Data block\n" + str(self.blenderObject.matrix_world) + "\n"

            # Debug code - this dumps the pre/post/bake matrix for every single xplane bone into the file.

            p = self
            while p != None:
               o += indent + '#   ' + p.getName() + '\n'
               o += str(p.getPreAnimationMatrix()) + '\n'
               o += str(p.getPostAnimationMatrix()) + '\n'
               o += str(p.getBakeMatrixForMyAnimations()) + '\n'
               p = None
            """
        isAnimated = self.isAnimated()
        hasAnimationAttributes = (
            self.xplaneObject != None and len(self.xplaneObject.animAttributes) > 0
        )

        if not isAnimated and not hasAnimationAttributes:
            return o

        # and postMatrix is not preMatrix
        if (isAnimated) or hasAnimationAttributes:
            o += indent + "ANIM_begin\n"

        if isAnimated:  # and postMatrix is not preMatrix:
            # write out static translations of bake
            bakeMatrix = self.getBakeMatrixForMyAnimations()
            o += self._writeStaticTranslation(bakeMatrix)
            o += self._writeStaticRotation(bakeMatrix)

            for dataref in sorted(list(self.animations.keys())):
                o += self._writeTranslationKeyframes(dataref)
            for dataref in sorted(list(self.animations.keys())):
                o += self._writeRotationKeyframes(dataref)

        o += self._writeAnimAttributes()

        return o

    def _writeStaticTranslation(self, bakeMatrix: mathutils.Matrix) -> None:
        debug = getDebug()
        indent = self.getIndent()
        o = ""

        bakeMatrix = bakeMatrix

        translation = bakeMatrix.to_translation()
        translation[0] = round(translation[0], 5)
        translation[1] = round(translation[1], 5)
        translation[2] = round(translation[2], 5)

        # ignore noop translations
        if translation[0] == 0 and translation[1] == 0 and translation[2] == 0:
            return o

        if debug:
            o += indent + "# static translation\n"

        o += indent + "ANIM_trans\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
            floatToStr(translation[0]),
            floatToStr(translation[2]),
            floatToStr(-translation[1]),
            floatToStr(translation[0]),
            floatToStr(translation[2]),
            floatToStr(-translation[1]),
        )

        return o

    def _writeStaticRotation(self, bakeMatrix: mathutils.Matrix) -> str:
        debug = getDebug()
        indent = self.getIndent()
        o = ""
        bakeMatrix = bakeMatrix
        rotation = list(
            map(
                lambda c: round(c, xplane_constants.PRECISION_KEYFRAME),
                bakeMatrix.to_euler("XYZ"),
            )
        )

        # ignore noop rotations
        if rotation == (0, 0, 0):
            return o

        if debug:
            o += indent + "# static rotation\n"

        # Ben says: this is SLIGHTLY counter-intuitive...Blender axes are
        # globally applied in a Euler, so in our XYZ, X is affected -by- Y
        # and both are affected by Z.
        #
        # Since X-Plane works opposite this, we are going to apply the
        # animations exactly BACKWARD! ZYX.  The order here must
        # be opposite the decomposition order above.
        #
        # Note that since our axis naming is ALSO different this will
        # appear in the OBJ file as Y -Z X.
        #
        # see also: http://hacksoflife.blogspot.com/2015/11/blender-notepad-eulers.html

        axes = (2, 1, 0)
        eulerAxes = [(0, 0, 1), (0, 1, 0), (1, 0, 0)]

        for i, axis in enumerate(eulerAxes):
            deg = math.degrees(rotation[axes[i]])

            # ignore zero rotation
            if not round(deg, xplane_constants.PRECISION_KEYFRAME) == 0:
                tab = "\t"
                o += (
                    f"{indent}ANIM_rotate"
                    f"\t{tab.join(map(floatToStr,vec_b_to_x(axis)))}"
                    f"\t{tab.join(map(floatToStr, [deg, deg]))}\n"
                )

        return o

    def _writeKeyframesLoop(self, dataref: str) -> str:
        o = ""

        if dataref in self.datarefs:
            if self.datarefs[dataref].loop > 0:
                indent = self.getIndent()
                o += f"{indent}\tANIM_keyframe_loop\t{self.datarefs[dataref].loop}\n"
        return o

    def _writeTranslationKeyframes(self, dataref: str) -> str:
        debug = getDebug()
        keyframes = self.animations[dataref]

        o = ""

        if not self.isDataRefAnimatedForTranslation():
            return o

        # Apply scaling to translations
        pre_loc, pre_rot, pre_scale = self.getPreAnimationMatrix().decompose()

        totalTrans = 0
        indent = self.getIndent()

        if debug:
            o += f"{indent}# translation keyframes\n"

        o += f"{indent}ANIM_trans_begin\t{dataref}\n"

        for keyframe in keyframes:
            totalTrans += sum(map(abs, keyframe.location))

            o += (
                f"{indent}ANIM_trans_key"
                f"\t{floatToStr(keyframe.dataref_value)}"
                f"\t{floatToStr(keyframe.location[0] * pre_scale[0])}"
                f"\t{floatToStr(keyframe.location[2] * pre_scale[2])}"
                f"\t{floatToStr(-keyframe.location[1] * pre_scale[1])}"
                f"\n"
            )

        o += self._writeKeyframesLoop(dataref)
        o += f"{indent}ANIM_trans_end\n"

        # do not write zero translations
        if totalTrans == 0:
            return ""

        return o

    def _writeAxisAngleRotationKeyframes(self, dataref, keyframes) -> str:
        o = ""
        indent = self.getIndent()
        totalRot = 0

        # our reference axis (or axes)
        axes, final_rotation_mode = keyframes.getReferenceAxes()

        if len(axes) == 3:
            # decompose to eulers and return euler rotation instead
            o = self._writeEulerRotationKeyframes(dataref, keyframes.asEuler())
            return o
        elif len(axes) == 1:
            refAxis = axes[0]

        tab = "\t"
        o += (
            f"{indent}ANIM_rotate_begin"
            f"\t{tab.join(map(floatToStr, vec_b_to_x(refAxis)))}"
            f"\t{dataref}\n"
        )

        for keyframe in keyframes:
            deg = math.degrees(keyframe.rotation[0])
            totalRot += abs(deg)

            o += f"{indent}ANIM_rotate_key\t{floatToStr(keyframe.dataref_value)}\t{floatToStr(deg)}\n"

        o += self._writeKeyframesLoop(dataref)
        o += f"{indent}ANIM_rotate_end\n"

        # do not write zero rotations
        if round(totalRot, xplane_constants.PRECISION_KEYFRAME) == 0:
            return ""

        return o

    def _writeQuaternionRotationKeyframes(self, dataref, keyframes) -> str:
        # Writing axis angle will automatically convert quaternions to AA and write it
        return self._writeAxisAngleRotationKeyframes(dataref, keyframes.asAA())

    def _writeEulerRotationKeyframes(self, dataref, keyframes) -> str:
        debug = getDebug()
        o = ""
        indent = self.getIndent()
        axes, final_rotation_mode = keyframes.getReferenceAxes()
        totalRot = 0

        for axis, order in zip(
            axes, XPlaneKeyframeCollection.EULER_AXIS_ORDERING[final_rotation_mode]
        ):
            ao = ""
            totalAxisRot = 0

            tab = "\t"
            ao += (
                f"{indent}ANIM_rotate_begin"
                f"\t{tab.join(map(floatToStr, vec_b_to_x(axis)))}"
                f"\t{dataref}\n"
            )

            for keyframe in keyframes:
                deg = math.degrees(keyframe.rotation[order])
                totalRot += abs(deg)
                totalAxisRot += abs(deg)
                ao += f"{indent}ANIM_rotate_key\t{floatToStr(keyframe.dataref_value)}\t{floatToStr(deg)}\n"

            ao += self._writeKeyframesLoop(dataref)
            ao += f"{indent}ANIM_rotate_end\n"

            # do not write non-animated axis
            if round(totalAxisRot, xplane_constants.PRECISION_KEYFRAME) > 0:
                o += ao

        # do not write zero rotations
        if round(totalRot, xplane_constants.PRECISION_KEYFRAME) == 0:
            return ""

        return o

    def _writeRotationKeyframes(self, dataref) -> str:
        debug = getDebug()
        keyframes = self.animations[dataref]
        o = ""

        if not self.isDataRefAnimatedForRotation():
            return o

        if debug:
            o += f"{self.getIndent()}# rotation keyframes\n"

        rotationMode = keyframes[0].rotationMode

        if rotationMode == "AXIS_ANGLE":
            o += self._writeAxisAngleRotationKeyframes(dataref, keyframes)
        elif rotationMode == "QUATERNION":
            o += self._writeQuaternionRotationKeyframes(dataref, keyframes)
        else:
            o += self._writeEulerRotationKeyframes(dataref, keyframes)

        return o

    def _writeAnimAttributes(self) -> str:
        o = ""

        if self.xplaneObject == None:
            return o

        for name in self.xplaneObject.animAttributes:
            attr = self.xplaneObject.animAttributes[name]
            for i in range(len(attr.value)):
                o += f"{self.getIndent()}{attr.name}\t{attr.getValueAsString(i=i)}\n"

        return o

    def writeAnimationSuffix(self) -> str:
        o = ""
        isAnimated = self.isAnimated()
        hasAnimationAttributes = (
            self.xplaneObject != None and len(self.xplaneObject.animAttributes) > 0
        )

        if not isAnimated and not hasAnimationAttributes:
            return o

        if (isAnimated) or hasAnimationAttributes:
            o += f"{self.getIndent()}ANIM_end\n"

        return o
