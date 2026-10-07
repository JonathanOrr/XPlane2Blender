"""
Writes an XPlaneLight: its LIGHT_* line, turned by a static ANIM_rotate when X-Plane would aim the light another
way than the Blender light points.
"""

import math
from typing import Tuple

import mathutils
from mathutils import Matrix, Vector

from io_xplane2blender import xplane_constants
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser

from ..xplane_config import getDebug
from ..xplane_constants import *
from ..xplane_helpers import floatToStr, vec_b_to_x, vec_x_to_b


class XPlaneLightWrite:
    """The writing half of XPlaneLight"""

    def write(self) -> None:
        debug = getDebug()
        indent = self.xplaneBone.getIndent()
        if self.lightType == LIGHT_NON_EXPORTING:
            return ""
        o = super().write()

        light_data = self.blenderObject.data
        try:
            parsed_light = xplane_lights_txt_parser.get_parsed_light(self.lightName)
        except KeyError:
            parsed_light = None

        bakeMatrix = self.xplaneBone.getBakeMatrixForAttached()
        translation = bakeMatrix.to_translation()
        has_anim = False

        def find_autocorrect_axis_angle(
            dir_vec_p_norm_b: Vector, bake_matrix: Matrix
        ) -> Tuple[Vector, float]:
            """
            Given a vector of where the light will be pointed in X-Plane and our real rotation,
            find the Axis-Angle for how we need to rotate via animation to make the difference
            """

            def clamp(num: float, minimum: float, maximum: float) -> float:
                if num < minimum:
                    return minimum
                elif num > maximum:
                    return maximum
                else:
                    return num

            # Multiple bake matrix by Vector to get the direction of the Blender object

            dir_vec_b_norm = self.get_light_direction_b()

            # P is start rotation, and B is stop. As such, we have our axis of rotation.
            # "We take the X-Plane light and turn it until it matches what the artist wanted"
            axis_angle_vec_b = dir_vec_p_norm_b.cross(dir_vec_b_norm)

            dot_product_p_b = dir_vec_p_norm_b.dot(dir_vec_b_norm)
            if dot_product_p_b < 0:
                axis_angle_theta = math.pi - math.asin(
                    clamp(axis_angle_vec_b.magnitude, -1.0, 1.0)
                )
            else:
                axis_angle_theta = math.asin(
                    clamp(axis_angle_vec_b.magnitude, -1.0, 1.0)
                )
            return axis_angle_vec_b, axis_angle_theta

        def should_autocorrect_preautomatic() -> bool:
            try:
                return (
                    self.lightType
                    in {
                        xplane_constants.LIGHT_NAMED,
                        xplane_constants.LIGHT_PARAM,
                    }
                    and not self.record_completed.is_omni()
                    # Yes, '!= "POINT"' matters for historical reasons
                    and light_data.type != "POINT"
                    and all(
                        param in self.record_completed for param in ["DX", "DY", "DZ"]
                    )
                )
            except (
                ValueError,
                AttributeError,
            ):  # is_omni not ready, self.record_completed is None
                return False

        def should_autocorrect_automatic() -> bool:
            try:
                is_omni = self.record_completed.is_omni()
            except (
                AttributeError,
                ValueError,
            ):  # self.record_completed is None, is_omni not ready
                is_omni = False

            if self.lightType == LIGHT_AUTOMATIC and not is_omni:
                if self.params:
                    # If we will be LIGHT_PARAM but we won't be filling in DXYZ ourselves
                    return all(param not in self.params for param in ["DX", "DY", "DZ"])
                elif self.record_completed:
                    # If we will be LIGHT_NAMED and our overload has DXYZ columns to correct
                    return all(
                        column in self.record_completed for column in ["DX", "DY", "DZ"]
                    )
            else:
                return False

        if should_autocorrect_preautomatic() or should_autocorrect_automatic():
            axis_angle_vec_b, axis_angle_theta = find_autocorrect_axis_angle(
                vec_x_to_b(
                    Vector(
                        self.record_completed[param] for param in ["DX", "DY", "DZ"]
                    ).normalized()
                ),
                bakeMatrix,
            )
            # Vector P(arameters), in Blender Space

            # Ben says: lights always have some kind of offset because the light itself
            # is "at" 0,0,0, so we treat the translation as the light position.
            # But if there is a ROTATION then in the light's bake matrix, the
            # translation is pre-rotation.  but we want to write a single static rotation
            # and then NOT write a translation every time.
            #
            # Inverse to change our animation order (so we really have rot, trans when we
            # originally had trans, rot) and now we can use the translation in the lamp
            # itself.
            if round(axis_angle_theta, PRECISION_KEYFRAME) != 0.0:
                o += f"{indent}ANIM_begin\n"

                if debug:
                    o += f"{indent}# static rotation\n"

                axis_angle_vec3_x = vec_b_to_x(axis_angle_vec_b).normalized()
                tab = "\t"
                anim_rotate_dir = (
                    f"{indent}ANIM_rotate"
                    f"\t{tab.join(map(floatToStr,axis_angle_vec3_x))}"
                    f"\t{floatToStr(math.degrees(axis_angle_theta))}"
                    f"\t{floatToStr(math.degrees(axis_angle_theta))}"
                    f"\n"
                )
                o += anim_rotate_dir

                rot_matrix = mathutils.Matrix.Rotation(
                    axis_angle_theta, 4, axis_angle_vec_b
                )
                translation = rot_matrix.inverted() @ translation
                has_anim = True
        else:
            # Basically, you're here if the light is
            # - unknown
            # - omni
            # - a real lights the user didn't want autocorrected
            #
            # No animation was emited and no change to self.record_completed/params made
            pass

        if isinstance(self.params, dict):
            assert all(
                isinstance(p, (int, float)) for p in self.params.values()
            ), f"One of {self.lightName} parameters did not get replaced in collect or write: {self.params}"
        if self.record_completed:
            assert all(
                isinstance(c, (float, int))
                or c.startswith(("NOOP", "sim"))
                or c.endswith("cd")
                for c in self.record_completed
            ), f"record_completed is not complete {self.record_completed}"

        translation_xp_str = " ".join(map(floatToStr, vec_b_to_x(translation)))
        known_named_automatic = (
            self.lightType == LIGHT_AUTOMATIC
            and parsed_light
            and not parsed_light.light_param_def
        )
        unknown_named_automatic = self.lightType == LIGHT_AUTOMATIC and not parsed_light
        if self.lightType == LIGHT_NAMED or (
            known_named_automatic or unknown_named_automatic
        ):
            o += f"{indent}LIGHT_NAMED\t{self.lightName} {translation_xp_str}\n"
        elif self.lightType == LIGHT_PARAM or (
            self.lightType == LIGHT_AUTOMATIC and parsed_light.light_param_def
        ):
            if self.lightType == LIGHT_AUTOMATIC:
                param_output = " ".join(
                    f"{floatToStr(v)}{'' if param != 'INTENSITY' else 'cd'}"
                    for param, v in self.params.items()
                )
            else:
                param_output = self.params
            o += (
                f"{indent}LIGHT_PARAM\t{self.lightName}"
                f" {translation_xp_str}"
                f" {param_output}"
                f"\n"
            )
        elif self.lightType == LIGHT_CUSTOM:
            o += (
                f"{indent}LIGHT_CUSTOM\t{translation_xp_str}"
                f" {' '.join(map(floatToStr,self.color))}"
                f" {' '.join(map(floatToStr,[self.energy, self.size]))}"
                f" {' '.join(map(floatToStr,self.uv))}"
                f" {self.dataref}\n"
            )
        elif self.lightType == LIGHT_SPILL_CUSTOM:
            o += f"{indent}LIGHT_SPILL_CUSTOM {translation_xp_str} {self.params}\n"

        if has_anim:
            o += f"{indent}ANIM_end\n"

        return o
