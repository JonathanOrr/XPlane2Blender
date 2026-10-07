"""
Checks of keyframes and of pairs of bones for the drag manipulators.
"""

from io_xplane2blender.xplane_constants import *
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types.xplane_bone import XPlaneBone


def check_bones_drag_detent_are_orthogonal(
    drag_axis_bone: XPlaneBone,
    detent_bone: XPlaneBone,
    log_errors=True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    if log_errors:
        assert manipulator

    drag_axis_translation_keyframe_table = next(
        iter(drag_axis_bone.animations.values())
    ).getTranslationKeyframeTable()

    detent_axis_translation_keyframe_table = next(
        iter(detent_bone.animations.values())
    ).getTranslationKeyframeTable()

    # Assuming that these are only rotating on a single axis
    drag_axis = (
        drag_axis_translation_keyframe_table[-1].location
        - drag_axis_translation_keyframe_table[0].location
    )
    detent_axis = (
        detent_axis_translation_keyframe_table[-1].location
        - detent_axis_translation_keyframe_table[0].location
    )

    dot_product = drag_axis.dot(detent_axis)

    if not -0.01 < dot_product < 0.01 and log_errors:
        logger.error(
            "Location animation for the {} manipulator attached to {} must not be along the main drag animation axis".format(
                manipulator.manip.get_effective_type_name(),
                detent_bone.getBlenderName(),
            )
        )
        return False
    else:
        return True


# X-Plane note: X-Plane implements the Drag Rotate manipulator using a system akin to polar co-ordinates.
# If the rotation axis is on Z, the detent can be draged any where in XY space. This will be translated into polar co-ordinates
# as angle, and distance is the distance draged from the origin.
# If the detent animation is animated at al on the Z axis, X-Plane won't drag there and it'll be a broken manipulator
#
# To detect this, we take the dot product between the rotation and detent axis to discover if there is any component along that axis
def check_bones_rotation_translation_animations_are_orthogonal(
    rotation_bone: XPlaneBone,
    child_bone: XPlaneBone,
    log_errors=True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    if log_errors:
        assert manipulator

    rotation_keyframe_table = (
        next(iter(rotation_bone.animations.values())).asAA().getRotationKeyframeTables()
    )

    rotation_axis = rotation_keyframe_table[0][0]

    child_values_cleaned = next(
        iter(child_bone.animations.values())
    ).getTranslationKeyframeTableNoClamps()

    child_axis = child_values_cleaned[1][1] - child_values_cleaned[0][1]

    dot_product = child_axis.dot(rotation_axis)
    if not -0.01 < dot_product < 0.01:
        logger.error(
            "Location animation for the {} manipulator attached to {} must not be along the rotation animation axis".format(
                manipulator.manip.get_effective_type_name(), child_bone.getBlenderName()
            )
        )
        return False
    else:
        return True


def _check_keyframe_translation_count(
    translation_bone: XPlaneBone,
    count: int,
    exclude_clamping: bool,
    cmp_func,
    cmp_error_msg: str,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    if log_errors:
        assert manipulator

    keyframe_col = next(iter(translation_bone.animations.values()))

    if exclude_clamping:
        res = cmp_func(len(keyframe_col.getTranslationKeyframeTableNoClamps()), count)
    else:
        res = cmp_func(len(keyframe_col.getTranslationKeyframeTable()), count)

    if not res:
        try:
            if log_errors:
                logger.error(
                    "{} manipulator attached to {} must have {} {} {}keyframes for its location animation".format(
                        manipulator.manip.get_effective_type_name(),
                        translation_bone.getBlenderName(),
                        cmp_error_msg,
                        count,
                        "non-clamping " if exclude_clamping else "",
                    )
                )
        except:
            if log_errors:
                logger.error(
                    "{} must have {} {} {}keyframes for its location animation".format(
                        translation_bone.getBlenderName(),
                        cmp_error_msg,
                        count,
                        "non-clamping " if exclude_clamping else "",
                    )
                )

        return False
    else:
        return True


def check_keyframe_translation_eq_count(
    translation_bone: XPlaneBone,
    count: int,
    exclude_clamping: bool,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    return _check_keyframe_translation_count(
        translation_bone,
        count,
        exclude_clamping,
        lambda x, y: x == y,
        "exactly",
        log_errors,
        manipulator,
    )


def check_keyframe_translation_ge_count(
    translation_bone: XPlaneBone,
    count: int,
    exclude_clamping: bool,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    return _check_keyframe_translation_count(
        translation_bone,
        count,
        exclude_clamping,
        lambda x, y: x >= y,
        "greater than or equal to",
        log_errors,
        manipulator,
    )


def check_keyframes_rotation_are_orderered(
    rotation_bone: XPlaneBone,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    if log_errors:
        assert manipulator

    rotation_keyframe_table = (
        next(iter(rotation_bone.animations.values())).asAA().getRotationKeyframeTables()
    )

    rotation_axis = rotation_keyframe_table[0][0]
    rotation_keyframe_data = rotation_keyframe_table[0][1]
    if not (
        rotation_keyframe_data == sorted(rotation_keyframe_data)
        or rotation_keyframe_data == sorted(rotation_keyframe_data, reverse=True)
    ):
        if log_errors:
            logger.error(
                "Rotation dataref values for the {} manipulator attached to {} are not in ascending or descending order".format(
                    manipulator.manip.get_effective_type_name(),
                    rotation_bone.getBlenderName(),
                )
            )
        return False
    else:
        return True


def check_manip_has_axis_detent_ranges(
    manipulator: "XPlaneManipulator", log_errors: bool = True
) -> bool:
    assert (
        manipulator.type == MANIP_DRAG_AXIS_DETENT
        or manipulator.type == MANIP_DRAG_ROTATE_DETENT
    )

    if not manipulator.manip.axis_detent_ranges:
        if log_errors:
            logger.error(
                "{} manipulator attached to {} must have axis detent ranges".format(
                    manipulator.type,
                    manipulator.xplanePrimative.xplaneBone.getBlenderName(),
                )
            )
        return False
    else:
        return True


def get_lift_at_max(translation_bone: XPlaneBone) -> float:
    translation_values_cleaned = next(
        iter(translation_bone.animations.values())
    ).getTranslationKeyframeTableNoClamps()
    return (
        translation_values_cleaned[1][1] - translation_values_cleaned[0][1]
    ).magnitude
