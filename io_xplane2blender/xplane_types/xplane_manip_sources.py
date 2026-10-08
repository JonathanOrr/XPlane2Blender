"""
Finds the bones a drag manipulator takes its motion from, walking up from the manipulator, and checks them.
"""

from typing import Callable, List, Optional, Tuple

from io_xplane2blender.xplane_constants import *
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types.xplane_bone import XPlaneBone

from .xplane_manip_bone_checks import (
    check_bone_has_n_datarefs,
    check_bone_is_animated_for_translation,
    check_bone_is_animated_on_n_axes,
    check_bone_is_not_animated_for_rotation,
)
from .xplane_manip_keyframe_checks import (
    check_keyframe_translation_eq_count,
    check_keyframes_rotation_are_orderered,
    check_keyframes_translation_on_a_line,
    check_manip_has_axis_detent_ranges,
)


def check_spec_drag_axis_bone(
    drag_axis_bone: XPlaneBone,
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    """
    Checks the drag_axis_bone. manip.type must be MANIP_AXIS_DETENT
    The bone must
        - have exactly 1 dataref
        - be animated for translation
        - have at least two non-clamping location keyframes, all on one line
        - not be animated for rotation
    """
    if log_errors:
        assert manipulator

    # This awesome clean code relies on short circuting to stop checking for problems
    # when a less specific error is detected
    if (
        drag_axis_bone
        and check_bone_has_n_datarefs(
            drag_axis_bone, 1, "location", log_errors, manipulator
        )
        and check_bone_is_animated_for_translation(
            drag_axis_bone, log_errors, manipulator
        )
        and check_keyframes_translation_on_a_line(
            drag_axis_bone, log_errors=True, manipulator=manipulator
        )
        and check_bone_is_not_animated_for_rotation(
            drag_axis_bone, log_errors, manipulator
        )
    ):
        return drag_axis_bone
    else:
        return None


def get_information_sources(
    manipulator: "XPlaneManipulator",
    white_list: Tuple[
        Tuple[
            Callable[[XPlaneBone, Optional[bool], Optional["XPlaneManipulator"]], bool],
            str,
        ]
    ],
    black_list: Tuple[
        Tuple[
            Callable[[XPlaneBone, Optional[bool], Optional["XPlaneManipulator"]], bool],
            str,
        ]
    ],
    log_errors: bool = True,
) -> Optional[List[XPlaneBone]]:
    """
    Starting at the manipulator's bone, walk up the tree of parents, ignoring bones that are completely unanimated,
    and testing animated bones that they're in the right sequence with the right types.

    Bones are checked against white_list and black_list predicates. For each bone, the white_list function and black_list must return True and False.  These functions must match the signature of
        def check_something(bone:XPlaneBone,log_errors:bool,manipulator:'XPlaneManipulator')->bool
    All logger errors will always be surpressed

    The 2nd part of the tuple is the type of animation it is testing. Currently this is just "location" or "rotation"

    Returns a list of collected bones or None if there was an error
    """

    def find_next_animated_bone(bone: XPlaneBone):
        # Note the use of blenderObject.xplane.datarefs, as opposed to bone.datarefs!
        while bone is not None:
            if bone.blenderBone is None:
                if len(bone.animations.values()) > 0 or (
                    bone.blenderObject
                    and list(
                        filter(
                            lambda d: d.anim_type == ANIM_TYPE_TRANSFORM,
                            bone.blenderObject.xplane.datarefs,
                        )
                    )
                ):
                    break
            else:
                if len(bone.animations.values()) > 0 or list(
                    filter(
                        lambda d: d.anim_type == ANIM_TYPE_TRANSFORM,
                        bone.blenderBone.xplane.datarefs,
                    )
                ):
                    break

            bone = bone.parent

        return bone

    def log_error(
        manipulator: "XPlaneManipulator",
        white_list: Tuple[
            Tuple[
                Callable[
                    [XPlaneBone, Optional[bool], Optional["XPlaneManipulator"]], bool
                ],
                str,
            ]
        ],
        black_list: Tuple[
            Tuple[
                Callable[
                    [XPlaneBone, Optional[bool], Optional["XPlaneManipulator"]], bool
                ],
                str,
            ]
        ],
        collected_bones: List[XPlaneBone],
        last_index: int,  # Since we allow gaps in the parent-child chain, idx != last_bone
        last_bone_examined: XPlaneBone,
        last_white_result: bool,
        last_black_result: bool,
    ):

        # Something, anything, has to be wrong in some way or this shouldn't have been called!
        assert (
            len(collected_bones) != len(white_list)
            or last_white_result
            or last_black_result
        )

        error_header = "Requirements for {manip_type} manipulator on '{manipulator_name}' are not met".format(
            manip_type=manipulator.manip.get_effective_type_name(),
            manipulator_name=manipulator.xplanePrimative.xplaneBone.getName(
                ignore_indent_level=True
            ),
        )

        type_requirements = """
Manipulator Type Requirements:
-----------------------------
"""
        type_requirements += "'{manip_type}' manipulators must have a {anim_type_white} animation or be a child of a {anim_type_white} animation".format(
            manip_type=manipulator.manip.get_effective_type_name(),
            anim_type_white=white_list[0][1].title(),
        )

        for i in range(len(white_list)):
            if i > 0:
                type_requirements += (
                    ", which must be a child of a {anim_type_white} animation".format(
                        anim_type_white=white_list[i][1].title()
                    )
                )

        animations_found = """
Matching Animations Found:
-------------------------
"""
        animations_found_strs = []
        for i, bone_and_type in enumerate(
            zip(
                collected_bones,
                [white_list_entry[1] for white_list_entry in white_list],
            )
        ):
            animations_found_strs.append(
                "- {anim_type_white} animation found on {bone_name}".format(
                    anim_type_white=bone_and_type[1].title(),
                    bone_name=bone_and_type[0].getName(ignore_indent_level=True),
                )
            )

        if animations_found_strs:
            animations_found += "\n".join(animations_found_strs)
        else:
            animations_found += "None"

        problems_found = """
Problems Found:
--------------
Stopped searching because
"""
        problems_found_strs = []
        if not white_list_result and last_bone_examined is not None:
            problems_found_strs.append(
                "- {anim_type_white} animation was not found on {name}".format(
                    anim_type_white=white_list[idx][1].title(),
                    name=last_bone_examined.getName(ignore_indent_level=True),
                )
            )

        if black_list_result:
            problems_found_strs.append(
                "- {anim_type_black} animation was found on {name}".format(
                    anim_type_black=black_list[idx][1].title(),
                    name=last_bone_examined.getName(ignore_indent_level=True),
                )
            )

        if last_bone_examined is None:
            problems_found_strs.append(
                "- {anim_count_str} found before exporter ran out of bones to inspect".format(
                    anim_count_str=(
                        "{} animation" + ("" if len(collected_bones) == 1 else "s")
                    ).format(len(collected_bones))
                )
            )

        problems_found += "\n".join(problems_found_strs)

        solutions_found = """
Possible Solutions:
------------------
"""
        solutions_found_strs = []
        if not white_list_result and last_bone_examined is not None:
            solutions_found_strs.append(
                "- Add {anim_type_white} animation to {name}".format(
                    anim_type_white=white_list[idx][1].title(),
                    name=last_bone_examined.getName(ignore_indent_level=True),
                )
            )

        if black_list_result:
            solutions_found_strs.append(
                "- Remove {anim_type_black} animation from {name}".format(
                    anim_type_black=black_list[idx][1].title(),
                    name=last_bone_examined.getName(ignore_indent_level=True),
                )
            )
        if last_bone_examined is None:
            solutions_found_strs.append(
                "- You may have missing animations, not enough objects or bones, or have incorrectly set up your parent-child relationships"
            )

        solutions_found_strs.append(
            "- Check the Manipulator Type Requirements above and online documentation for more details"
        )
        solutions_found += "\n".join(solutions_found_strs)

        logger.error(
            error_header
            + "\n".join(
                [type_requirements, animations_found, problems_found, solutions_found]
            )
        )

    idx = 0
    collected_bones = []
    current_bone = manipulator.xplanePrimative.xplaneBone

    while current_bone is not None and idx < len(white_list):
        current_bone = find_next_animated_bone(current_bone)
        found_error = False
        white_list_result = False
        black_list_result = False
        if current_bone is None:
            found_error = True
            break
        else:
            white_list_result = white_list[idx][0](current_bone, False)
            black_list_result = black_list[idx][0](current_bone, False)

            if not white_list_result or black_list_result:
                found_error = True
                break
            else:
                collected_bones.append(current_bone)
                current_bone = current_bone.parent
                idx += 1

        if found_error and log_errors:
            break

    if (found_error or len(collected_bones) != len(white_list)) and log_errors:
        log_error(
            manipulator,
            white_list,
            black_list,
            collected_bones,
            last_index=idx,
            last_bone_examined=current_bone,
            last_white_result=white_list_result,
            last_black_result=black_list_result,
        )
        return None

    return collected_bones


def check_spec_rotation_bone(
    bone: XPlaneBone, log_errors: bool = True, manipulator=None
) -> bool:
    """
    Checks the rotation bone. bones should come in from leaf towards root:
    - R for Drag Rotate,
    - T->R for Drag Rotate With Detents.
    Bones must not be none and already checked to be animated for rotation.
    manipulator.type must be MANIP_DRAG_ROTATE or MANIP_DRAG_ROTATE_DETENT

    The bone must
        - be animated for rotation
        - have exactly 1 dataref
        - rotate on exactly 1 axis of rotation
        - keyframes are ordered
    """

    if log_errors:
        assert manipulator

    # TODO: Is this still true with new white_list functions?
    # check_keyframe_rotation_ge_count is guaranteed to be true by isDataRefAnimatedForRotation, so we skip it
    if (
        check_bone_has_n_datarefs(bone, 1, "rotation", log_errors, manipulator)
        and check_bone_is_animated_on_n_axes(bone, 1, log_errors, manipulator)
        and check_keyframes_rotation_are_orderered(bone, log_errors, manipulator)
    ):
        return True

    return False


def check_spec_detent_bone(
    detent_bone: Tuple[XPlaneBone],
    log_errors: bool = True,
    manipulator: "XPlaneManipulator" = None,
) -> bool:
    """
    Checks the detent_bone.
    - T for MANIP_AXIS_DETENT
    - T, R for MANIP_DRAG_ROTATE_DETENT
     Bones must not be none and already checked to be animated for translation
     manip.type must be MANIP_AXIS_DETENT or MANIP_DRAG_ROTATE_DETENT

    The bone must
        - have an animated translation/rotation_bone for a parent (take care of by get_information_sources)
        - have exactly 1 dataref
        - be animated for translation
        - have at least two non-clamping location keyframes, all on one line
        - not be animated for rotation
    """

    # This awesome clean code relies on short circuting to stop checking for problems
    # when a less specific error is detected
    if (
        check_bone_has_n_datarefs(detent_bone, 1, "location", log_errors, manipulator)
        and check_bone_is_animated_for_translation(detent_bone, log_errors, manipulator)
        and check_keyframe_translation_eq_count(
            detent_bone,
            count=2,
            exclude_clamping=True,
            log_errors=True,
            manipulator=manipulator,
        )
        and check_bone_is_not_animated_for_rotation(
            detent_bone, log_errors, manipulator
        )
        and check_manip_has_axis_detent_ranges(manipulator, log_errors)
    ):
        return True
    else:
        return False
