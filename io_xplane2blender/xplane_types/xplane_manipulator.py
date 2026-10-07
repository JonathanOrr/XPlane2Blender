"""
Click zones (manipulators): checks a part's click settings and adds its ATTR_manip_* lines.

Most kinds write their settings as they are. The drag kinds that follow animation (drag along, drag along with
detents, drag rotate, drag rotate with detents) take their axis, values and detents from the animated bones above
the part: see xplane_manip_sources for how those bones are found and checked.
"""

from typing import Tuple, Union

from io_xplane2blender import xplane_helpers
from io_xplane2blender.xplane_constants import *
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types.xplane_attribute import XPlaneAttribute
from io_xplane2blender.xplane_types.xplane_bone import XPlaneBone

from .xplane_manip_bone_checks import (
    check_bone_is_animated_for_rotation,
    check_bone_is_animated_for_translation,
)
from .xplane_manip_detents import validate_axis_detent_ranges
from .xplane_manip_keyframe_checks import (
    check_bones_drag_detent_are_orthogonal,
    check_bones_rotation_translation_animations_are_orthogonal,
    get_lift_at_max,
)
from .xplane_manip_sources import (
    check_spec_detent_bone,
    check_spec_drag_axis_bone,
    check_spec_rotation_bone,
    get_information_sources,
)

# The settings each kind writes, in order, when they are written as they are
SETTINGS_WRITTEN = {
    MANIP_DRAG_XY: (
        "cursor",
        "dx",
        "dy",
        "v1_min",
        "v1_max",
        "v2_min",
        "v2_max",
        "dataref1",
        "dataref2",
        "tooltip",
    ),
    MANIP_DRAG_AXIS: ("cursor", "dx", "dy", "dz", "v1", "v2", "dataref1", "tooltip"),
    MANIP_DRAG_AXIS_PIX: (
        "cursor",
        "dx",
        "step",
        "exp",
        "v1",
        "v2",
        "dataref1",
        "tooltip",
    ),
    MANIP_COMMAND: ("cursor", "command", "tooltip"),
    MANIP_COMMAND_AXIS: (
        "cursor",
        "dx",
        "dy",
        "dz",
        "positive_command",
        "negative_command",
        "tooltip",
    ),
    **dict.fromkeys(
        (
            MANIP_COMMAND_KNOB,
            MANIP_COMMAND_SWITCH_UP_DOWN,
            MANIP_COMMAND_SWITCH_LEFT_RIGHT,
        ),
        ("cursor", "positive_command", "negative_command", "tooltip"),
    ),
    **dict.fromkeys(
        (
            MANIP_COMMAND_KNOB2,
            MANIP_COMMAND_SWITCH_UP_DOWN2,
            MANIP_COMMAND_SWITCH_LEFT_RIGHT2,
        ),
        ("cursor", "command", "tooltip"),
    ),
    MANIP_PUSH: ("cursor", "v_down", "v_up", "dataref1", "tooltip"),
    MANIP_RADIO: ("cursor", "v_down", "dataref1", "tooltip"),
    MANIP_TOGGLE: ("cursor", "v_on", "v_off", "dataref1", "tooltip"),
    **dict.fromkeys(
        (MANIP_DELTA, MANIP_WRAP),
        ("cursor", "v_down", "v_hold", "v1_min", "v1_max", "dataref1", "tooltip"),
    ),
    **dict.fromkeys(
        (MANIP_AXIS_KNOB, MANIP_AXIS_SWITCH_UP_DOWN, MANIP_AXIS_SWITCH_LEFT_RIGHT),
        ("cursor", "v1", "v2", "click_step", "hold_step", "dataref1", "tooltip"),
    ),
    MANIP_NOOP: (),
}

# The direction of a drag (written 2nd to 4th) is never rounded
DIRECTION = (1, 2, 3)


def _formatted(
    value: Tuple[Union[float, int, str], ...], unrounded: Tuple[int, ...]
) -> Tuple:
    return tuple(
        f"{v:.3f}" if isinstance(v, float) and i not in unrounded else v
        for i, v in enumerate(value)
    )


def _translation_frames(bone: XPlaneBone):
    return next(iter(bone.animations.values())).getTranslationKeyframeTableNoClamps()


class XPlaneManipulator:
    """
    This psuedo-XPlaneObject only has a collect method,
    which validates the manipulator data and adds it to xplanePrimitive's
    cockpitAttributes list
    """

    def __init__(self, xplanePrimative: "XPlanePrimitive"):
        assert xplanePrimative is not None

        self.manip = xplanePrimative.blenderObject.xplane.manip
        self.type = self.manip.type
        self.xplanePrimative = xplanePrimative

    def _add(self, name: str, value) -> None:
        self.xplanePrimative.cockpitAttributes.add(XPlaneAttribute(name, value))

    def collect(self) -> None:
        """Adds the click zone's lines. Stops, after logging why, at the first problem found"""
        if not self.manip.enabled:
            return
        if self.type in (MANIP_DRAG_ROTATE, MANIP_DRAG_ROTATE_DETENT):
            written = self._drag_rotate()
        elif self.type == MANIP_DRAG_AXIS_DETENT or (
            self.type == MANIP_DRAG_AXIS and self.manip.autodetect_settings_opt_in
        ):
            written = self._drag_axis()
        elif self.type in SETTINGS_WRITTEN:
            value = tuple(
                getattr(self.manip, setting) for setting in SETTINGS_WRITTEN[self.type]
            )
            self._add("ATTR_manip_" + self.type, _formatted(value, ()))
            written = True
        else:
            msg = "Manipulator type %s is unknown or unimplemented" % self.type
            logger.error(msg)
            raise Exception(msg)

        if (
            written
            and self.type in MANIPULATORS_MOUSE_WHEEL
            and self.manip.wheel_delta != 0
        ):
            self._add("ATTR_manip_wheel", f"{self.manip.wheel_delta:.3f}")

    def _drag_axis(self) -> bool:
        """
        Drag Axis (Opt In)/Drag Axis With Detents
        Empty/Bone -> Main drag axis animation and (optionally) v1_min/max for validating axis_detent_ranges
        |_Child mesh -> Manipulator settings and (optionally) detent axis animation

        Common Rules:
        - *Animations must only be driven by only 1 dataref
        - *Animations must have exactly 2 (non-clamping) keyframes

        Special rules for the Detent Bone:
        - Must be a leaf bone (checked in XPlanePrimative.write)
        - * Must have a parent with translation
        - * The positions at each keyframe must not be the same, including both being 0
        - The parent and translation animations are orthogonal
        - Must have axis detent ranges

        * (guarenteed by get_tranlation_bone)

        Semantically speaking we don't have a new manipulator type. The magic is in ATTR_axis_detented
        """
        moves = (check_bone_is_animated_for_translation, "location")
        turns = (check_bone_is_animated_for_rotation, "rotation")
        bones = 1 if self.type == MANIP_DRAG_AXIS else 2
        info_sources = get_information_sources(self, (moves,) * bones, (turns,) * bones)
        if not info_sources:
            return False
        drag_axis_bone = info_sources[-1]
        detent_axis_bone = info_sources[0] if bones == 2 else None
        if not check_spec_drag_axis_bone(
            drag_axis_bone, log_errors=True, manipulator=self
        ):
            return False

        # bone.animations - <DataRef,List<KeyframeCollection>>
        frames = _translation_frames(drag_axis_bone)
        drag_axis_xp = xplane_helpers.vec_b_to_x(
            frames[1].location - frames[0].location
        )
        # For use when validating axis detent ranges
        v1_min, v1_max = frames[0].value, frames[1].value

        lift_at_max = 0.0
        if detent_axis_bone:
            if not check_spec_detent_bone(
                detent_axis_bone, log_errors=True, manipulator=self
            ):
                return False
            lift_at_max = get_lift_at_max(detent_axis_bone)
            if round(lift_at_max, 5) == 0.0:
                logger.error(
                    f"{detent_axis_bone.getBlenderName()}'s detent animation has keyframes but no change between them"
                )
                return False
            if not check_bones_drag_detent_are_orthogonal(
                drag_axis_bone, detent_axis_bone, log_errors=True, manipulator=self
            ):
                return False

        if self.manip.autodetect_datarefs:
            self.manip.dataref1 = next(iter(drag_axis_bone.animations))

        value = (
            self.manip.cursor,
            *drag_axis_xp,
            v1_min,
            v1_max,
            self.manip.dataref1,
            self.manip.tooltip,
        )
        self._add("ATTR_manip_" + MANIP_DRAG_AXIS, _formatted(value, DIRECTION))
        if detent_axis_bone is None:
            return True
        self._axis_detented(detent_axis_bone)
        return self._detent_ranges(detent_axis_bone, v1_min, v1_max, lift_at_max)

    def _axis_detented(self, detent_axis_bone: XPlaneBone) -> None:
        if self.manip.autodetect_datarefs:
            # A nice little bit of useability for if someone disables autodetect datarefs
            self.manip.dataref2 = next(iter(detent_axis_bone.animations))
        frames = _translation_frames(detent_axis_bone)
        detent_axis_xp = xplane_helpers.vec_b_to_x(
            frames[1].location - frames[0].location
        )
        self._add(
            "ATTR_axis_detented",
            (*detent_axis_xp, frames[0].value, frames[1].value, self.manip.dataref2),
        )

    def _detent_ranges(
        self,
        translation_bone: XPlaneBone,
        v1_min: float,
        v1_max: float,
        lift_at_max: float,
    ) -> bool:
        ranges = self.manip.axis_detent_ranges
        if len(ranges) > 0 and not validate_axis_detent_ranges(
            ranges,
            translation_bone,
            v1_min,
            v1_max,
            lift_at_max,
            self.manip.get_effective_type_name(),
        ):
            return False
        for detent in ranges:
            self._add(
                "ATTR_axis_detent_range",
                tuple(f"{v:.3f}" for v in (detent.start, detent.end, detent.height)),
            )
        return True

    def _drag_rotate(self) -> bool:
        """
        Drag rotate manipulators must follow either one of two patterns
        1. The manipulator is attached to a translating XPlaneBone which has a rotating parent bone (MANIP_DRAG_ROTATE_DETENT)
        2. The manipulator is attached to a rotation bone (MANIP_DRAG_ROTATE)

        Common (and guaranteed by get_information_sources, and check_(rotation|translation)_bone)
        - *If a bone is used, it must be animated
        - *Animations must be driven by exactly 1 dataref

        Special rules for the Rotation Bone:
        - Can only be rotated around one axis, no matter the rotation mode
        - Rotation keyframe tables must be sorted in ascending or decending order
        - Rotation keyframe table must have at least 2 non-clamping rotation keyframes
        - 0 degree rotation not allowed (taken care of by isDataRefAnimatedForRotation)
        - Clockwise and counterclockwise rotations are supported

        Special rules for Translation Bone:
        - Must be a leaf bone (checked in XPlanePrimative.write)
        - *Must have a parent with rotation
        - **Cannot have rotation keyframes
        - **Must have exactly 2 (non-clamping) keyframes
        - Must not animate along rotation bone's axis
        - The positions at each keyframe must not be the same, including both being 0
        - Axis Detent ranges are mandatory (see validate_axis_detent_ranges)

         * (guaranteed by get_information_sources)
         ** (checked in check_detent_bone)
        """
        moves = (check_bone_is_animated_for_translation, "location")
        turns = (check_bone_is_animated_for_rotation, "rotation")
        if self.type == MANIP_DRAG_ROTATE:
            info_sources = get_information_sources(
                self, (turns,), (moves,), log_errors=True
            )
        else:
            info_sources = get_information_sources(
                self, (moves, turns), (turns, moves), log_errors=True
            )
        if info_sources is None:
            return False
        rotation_bone = info_sources[-1]
        translation_bone = (
            info_sources[0] if self.type == MANIP_DRAG_ROTATE_DETENT else None
        )

        if not check_spec_rotation_bone(
            rotation_bone, log_errors=True, manipulator=self
        ):
            return False

        lift_at_max = 0.0
        if translation_bone is not None:
            if not check_spec_detent_bone(
                translation_bone, log_errors=True, manipulator=self
            ):
                return False
            lift_at_max = get_lift_at_max(translation_bone)
            if round(lift_at_max, 5) == 0.0:
                logger.error(
                    f"{translation_bone.getBlenderName()}'s detent animation has keyframes but no change between them"
                )
                return False
            if not check_bones_rotation_translation_animations_are_orthogonal(
                rotation_bone, translation_bone, log_errors=True, manipulator=self
            ):
                return False

        if self.manip.autodetect_datarefs:
            self.manip.dataref1 = next(iter(rotation_bone.datarefs))
            self.manip.dataref2 = (
                next(iter(translation_bone.datarefs))
                if translation_bone is not None
                else "none"
            )

        rotation_origin_xp = xplane_helpers.vec_b_to_x(
            rotation_bone.getBlenderWorldMatrix().to_translation()
        )
        kf_collection = next(iter(rotation_bone.animations.values()))
        # If AA, we'll find the 1st table in a list of one
        # if Euler we'll find the only table with entries
        rotation_axis, rotation_table = next(
            sub_table
            for sub_table in kf_collection.getRotationKeyframeTablesNoClamps()
            if sub_table.table
        )
        rotation_axis_xp = xplane_helpers.vec_b_to_x(rotation_axis)

        v1_min, angle1 = rotation_table[0]
        v1_max, angle2 = rotation_table[-1]
        # Keyframes must differ and be in order (angle1 = 0, angle2 = 360 is legal, X-Plane interpolates between them)
        assert round(angle1, 5) != round(angle2, 5), "How did we get here?"
        if v1_min == v1_max:
            logger.error(
                f"{rotation_bone.getBlenderName()}'s Dataref 1's minimum cannot equal Dataref 1's maximum"
            )
            return False

        value = (
            self.manip.cursor,
            *rotation_origin_xp[:3],
            *rotation_axis_xp[:3],
            angle1,
            angle2,
            lift_at_max,
            v1_min,
            v1_max,
            0.0,  # v2_min
            lift_at_max,  # v2_max
            self.manip.dataref1,
            self.manip.dataref2,
            self.manip.tooltip,
        )
        self._add("ATTR_manip_" + MANIP_DRAG_ROTATE, _formatted(value, DIRECTION))

        if translation_bone is not None and not self._detent_ranges(
            translation_bone, v1_min, v1_max, lift_at_max
        ):
            return False
        for rot_keyframe in rotation_table[1:-1]:
            self._add("ATTR_manip_keyframe", (rot_keyframe.value, rot_keyframe.degrees))
        return True
