"""
Checks of single bones for the drag manipulators: datarefs, parents and how a bone is animated.

Some of these check_* methods break the rule of "no side effects in a boolean expression" when log_errors = True
However, without this, the logic must be duplicated, making it, in my opinion, worth it.

In addition, in order to give better error messages, some less used aspects of the data model are used. For instance,
using bone.datarefs instead of bone.animations for check_bone_has_n_datarefs
"""

from io_xplane2blender.xplane_constants import *
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types.xplane_bone import XPlaneBone


def check_bone_has_n_datarefs(
    bone: XPlaneBone,
    num_datarefs: int,
    anim_type: str,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    """
    Checks animations dict, not datarefs dictionary because we're looking for the actual animation
    that will be considered for the OBJ, and the datarefs dictionary is not guaranteed to be semantically
    the same thing.
    """
    if log_errors:
        assert manipulator

    assert bone

    if len(bone.datarefs) != num_datarefs:
        try:
            if log_errors:
                logger.error(
                    "The {} animation for the {} manipulator attached to {} must have exactly {} datarefs for its animation".format(
                        anim_type,
                        manipulator.manip.get_effective_type_name(),
                        bone.getBlenderName(),
                        num_datarefs,
                    )
                )
        except:
            if log_errors:
                logger.error(
                    "The {} animation for {} must have exactly {} datarefs for its animation".format(
                        anim_type, bone.getBlenderName(), num_datarefs
                    )
                )

        return False
    else:
        return True


def check_bone_has_parent(
    bone: XPlaneBone, log_errors: bool = True, manipulator: "XPlaneManipulator" = None
) -> bool:
    if log_errors:
        assert manipulator

    if bone.parent is None:
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must have a parent".format(
                    manipulator.manip.get_effective_type_name(), bone.getblendername()
                )
            )
        return False
    else:
        return True


def check_bone_is_animated_for_rotation(
    bone: XPlaneBone, log_errors: bool = True, manipulator: "XPlaneManipulator" = None
) -> bool:
    """
    Returns true if bone has at least two rotation keyframes that are different
    """
    if log_errors:
        assert manipulator

    assert bone is not None

    # Unfortunately this does not answer if we have one rotation keyframe, which, semantically
    # we are checking for. This makes us never able to really get a good error message for
    # "test_5_must_have_at_least_2_non_clamping_keyframes  See bug #333
    #
    # While it would nice to use the RotationKeyframeTable, we don't know if that can
    # be generated yet, a call to getReferenceAxes could fail if forced
    if not bone.isDataRefAnimatedForRotation():
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must have at least 2 rotation keyframes that are not the same".format(
                    manipulator.manip.get_effective_type_name(), bone.getBlenderName()
                )
            )
        return False
    else:
        return True


def check_bone_is_animated_for_translation(
    bone: XPlaneBone, log_errors: bool = True, manipulator: "XPlaneManipulator" = None
) -> bool:
    """
    Returns true if bone has at least two translation keyframes that are different
    """
    if log_errors:
        assert manipulator

    assert bone is not None
    if not bone.isDataRefAnimatedForTranslation():
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must have at least 2 translation keyframes that are not the same".format(
                    manipulator.manip.get_effective_type_name(), bone.getBlenderName()
                )
            )
        return False
    else:
        return True


def check_bone_is_animated_on_n_axes(
    bone: XPlaneBone,
    num_axis_of_rotation: int,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    if log_errors:
        assert manipulator

    rotation_keyframe_table = next(
        iter(bone.animations.values())
    ).getRotationKeyframeTables()

    if len(rotation_keyframe_table) == 3:
        deg_per_axis = []
        for axis, table in rotation_keyframe_table:
            deg_per_axis.append(sum([abs(keyframe.degrees) for keyframe in table]))

        real_num_axis_of_rotation = len(
            (
                *filter(
                    lambda total_rotations: round(total_rotations, 8) != 0.0,
                    deg_per_axis,
                ),
            )
        )
    else:
        real_num_axis_of_rotation = len(rotation_keyframe_table)

    # The sum of the degrees rotated along each axis over every keyframe sorted from lowest-to-highest
    # should be 0,0,T. Having a second or all three rotating would mean that at least the second entry would be not 0
    if real_num_axis_of_rotation != num_axis_of_rotation:
        if log_errors:
            logger.error(
                "{} manipulator attached to {} can only rotate around {} axis".format(
                    manipulator.manip.get_effective_type_name(),
                    bone.getBlenderName(),
                    num_axis_of_rotation,
                )
            )
        return False
    else:
        return True


def check_bone_is_leaf(
    bone: XPlaneBone, log_errors: bool = True, manipulator: "XPlaneManipulator" = None
) -> bool:
    if log_errors:
        assert manipulator

    if len(bone.children) > 0:
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must have no children".format(
                    manipulator.manip.get_effective_type_name(), bone.getBlenderName()
                )
            )
        return False
    else:
        return True


def check_bone_is_not_animated_for_rotation(
    bone: XPlaneBone, log_errors: bool = True, manipulator: "XPlaneManipulator" = None
) -> bool:
    if log_errors:
        assert manipulator

    if check_bone_is_animated_for_rotation(bone, log_errors=False):
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must not have rotation keyframes".format(
                    manipulator.manip.get_effective_type_name(), bone.getBlenderName()
                )
            )
        return False
    else:
        return True


def check_bone_is_not_animated_for_translation(
    bone: XPlaneBone, log_errors: bool = True, manipulator: "XPlaneManipulator" = None
) -> bool:
    if log_errors:
        assert manipulator

    if check_bone_is_animated_for_translation(bone, log_errors, manipulator):
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must not have location keyframes".format(
                    manipulator.manip.get_effective_type_name(), bone.getBlenderName()
                )
            )
        return False
    else:
        return True


def check_bone_parent_is_animated_for_rotation(
    bone: XPlaneBone, log_errors: bool = True
) -> bool:
    assert bone.parent
    if not check_bone_is_animated_for_rotation(bone.parent, False):
        if log_errors:
            logger.error(
                "{}'s parent {} must be animated with rotation".format(
                    bone.getBlenderName(), bone.parent.getBlenderName()
                )
            )
        return False
    else:
        return True


def check_bone_parent_is_animated_for_translation(
    bone: XPlaneBone, log_errors: bool = True
) -> bool:
    assert bone.parent
    if not check_bone_is_animated_for_translation(bone.parent, log_errors, manipulator):
        if log_errors:
            logger.error(
                "{}'s parent {} must be animated with location keyframes".format(
                    bone.getBlenderName(), bone.parent.getBlenderName()
                )
            )
        return False
    else:
        return True
