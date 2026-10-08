"""
Collecting each kind of X-Plane light: checks it against lights.txt and works out the parameters it will be written
with. The tables before each kind say what happens for every combination.
"""

import math
from itertools import takewhile, tee
from typing import Optional

from mathutils import Vector

from io_xplane2blender.xplane_constants import PRECISION_KEYFRAME
from io_xplane2blender.xplane_helpers import logger, vec_b_to_x
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as lights_txt


def width_for_billboard(spot_size: float) -> float:
    assert spot_size != 0, "spot_size is 0, divide by zero error will occur"
    angle_from_center = spot_size / 2
    return math.cos(angle_from_center) / (math.cos(angle_from_center) - 1)


def dir_mag_for_billboard(spot_size: float) -> float:
    return 1 - width_for_billboard(spot_size)


def width_for_spill(spot_size: float) -> float:
    """cos(half the cone angle)"""
    return max(0.0, math.cos(spot_size * 0.5))


def _is_number_ish(arg) -> bool:
    if not isinstance(arg, str):
        return True
    if len(arg) >= 3:
        if arg[-2:] == "cd":
            try:
                int(arg[:-2])
                return True
            except ValueError:
                return False
    else:
        try:
            int(arg[:-2])
            return True
        except ValueError:
            return False


class XPlaneLightCollect:
    """The collecting half of XPlaneLight"""

    def _warn_unknown_name(self) -> None:
        logger.warn(
            f"\"{self.blenderObject.name}\"'s Light Name '{self.lightName}' is unknown,"
            f" check your spelling or update your lights.txt file"
        )

    def _complete_best_overload(self, parsed_light) -> None:
        self.record_completed = parsed_light.best_overload()
        if lights_txt.ColumnName.DREF in self.record_completed.prototype():
            self.record_completed.apply_sw_callback()

    # X-Plane Light Type | Light Type | parsed_light | light_param_defs | Result
    # -------------------|------------|--------------|------------------|-------
    # LIGHT_NAMED        | *          | Yes          | Yes              | Error, "known param used as named light"
    # LIGHT_NAMED        | "POINT"    | Yes          | No               | Apply sw_callback, do not do autocorrect (POINT means OMNI)
    # LIGHT_NAMED        | not "POINT"| Yes          | No               | Apply sw_callback if possible, autocorrect
    # LIGHT_NAMED        | *          | No           | N/A              | Treat as unknown named light, Warning given, NAMED written as is, no SW callbacks applied
    def _collect_named(self, parsed_light: Optional[lights_txt.ParsedLight]) -> None:
        if parsed_light and parsed_light.light_param_def:
            logger.error(
                f"Light name {self.lightName} is a known param light, being used as a name light."
                f" Check the light name or light type"
            )
        elif parsed_light:
            self._complete_best_overload(parsed_light)
        else:
            self._warn_unknown_name()

    # X-Plane Light Type | Light Type | parsed_light | light_param_defs | Result
    # -------------------|------------|--------------|------------------|-------
    # LIGHT_PARAM        | "POINT"    | Yes          | Yes              | Parse params, replace self.params_complete
    # LIGHT_PARAM        | not "POINT"| Yes          | Yes              | Parse params, replace self.params_complete, apply sw_callback if possible. Autocorrect with ANIM_
    # LIGHT_PARAM        | *          | Yes          | No               | Error, "known named light used as a param light"
    # LIGHT_PARAM        | *          | No           | N/A              | Warning given, PARAMS written as is, no auto correction_applied
    def _collect_param(self, parsed_light: Optional[lights_txt.ParsedLight]) -> None:
        if parsed_light and parsed_light.light_param_def:
            self._check_param_light(parsed_light)
        elif parsed_light:
            logger.error(
                f"Light name {self.lightName} is a named light, not a param light."
                f" Check the light type drop down menu"
            )
        else:
            # Even if we don't know the PARAM light, we still have to check if we're about to write out no params
            self._warn_unknown_name()
            if not self.blenderObject.data.xplane.params.split():
                logger.error(f"'{self.blenderObject.name}' has an empty parameters box")

    def _check_param_light(self, parsed_light: lights_txt.ParsedLight) -> None:
        """
        Validation/apply_sw_callback only, LIGHT_PARAM type inserts xplane.params content directly into the OBJ
        """
        params_formal = parsed_light.light_param_def

        # Parsed params from the params box, stripped and ignoring the comment.
        # Make the actual parameters, if there are <= than params_formal, its okay
        # if here are more we have a comment.
        params_actual = []
        params_itr = iter(self.blenderObject.data.xplane.params.lstrip())
        while len(params_actual) < len(params_formal):
            try:
                n, params_itr = tee(params_itr)
                next(n)
            except StopIteration:
                break
            else:
                actual = "".join(takewhile(lambda c: not c.isspace(), params_itr))
                if actual:
                    params_actual.append(actual)
        self.comment = "".join(params_itr).lstrip()

        if len(params_actual) < len(params_formal):
            logger.error(
                f"'{self.blenderObject.name}':Not enough actual parameters ('{' '.join(params_actual)}') to"
                f" satisfy 'LIGHT_PARAM_DEF {len(params_formal)} {' '.join(params_formal)}'"
            )
            return

        if self.comment and not self.comment.startswith(("//", "#")):
            logger.warn(
                f"Comment in param light ({self.comment}) does not start with '//' or '#'"
            )

        self.record_completed = parsed_light.best_overload()
        for i, (pformal, pactual) in enumerate(zip(params_formal, params_actual)):
            # X-Plane 12 intensities are written with a unit, like 500cd
            number = pactual[:-2] if pactual.endswith("cd") else pactual
            try:
                float(number)
            except ValueError:
                logger.error(
                    f"Parameter {i} ({pactual}) of {self.blenderObject.name} is not a number"
                )
                return
            try:
                self.record_completed.replace_parameterization_argument(
                    pformal, float(number)
                )
            except ValueError:
                continue

        if lights_txt.ColumnName.DREF in self.record_completed.prototype():
            self.record_completed.apply_sw_callback()

        # The only prototypes without DXYZ are SPILL_GND/_REV (of which there are no parameters)
        # and SPILL_HW_FLA overloads, which are in fact omni, but none of them are parameterized
        try:
            dir_vec = Vector(map(self.record_completed.__getitem__, ["DX", "DY", "DZ"]))
        except KeyError:
            dir_vec = Vector((0, 0, 0))
        try:
            # We use precision keyframe because we don't want to animate unnecissarily
            if (
                round(dir_vec.magnitude, PRECISION_KEYFRAME) == 0.0
                and not self.record_completed.is_omni()
            ):
                logger.error(
                    f"{self.blenderObject.name}'s '{self.lightName}' is directional, but has (0, 0, 0) for direction"
                )
        except ValueError:  # is_omni not ready yet
            pass

    # X-Plane Light Type | Light Type | parsed_light | light_param_defs | Result
    # -------------------|------------|--------------|------------------|-------
    # LIGHT_AUTOMATIC    |"POINT/SPOT"| Yes          | Yes              | Fill out params, apply any sw_callbacks, and write
    # LIGHT_AUTOMATIC    |"POINT/SPOT"| Yes          | No               | Treat as named light, apply any sw_callbacks, write
    # LIGHT_AUTOMATIC    |"POINT/SPOT"| No           | N/A              | Treat as named light, give warning, write as is
    # LIGHT_AUTOMATIC    | Any Others | N/A          | N/A              | Error, "Automatic lights require POINT or SPOT"
    # LIGHT_AUTOMATIC    |"POINT/SPOT"| Incompatible | N/A              | Error, "Light is incompatible", a label in the UI should also mention this
    def _collect_automatic(
        self, parsed_light: Optional[lights_txt.ParsedLight]
    ) -> None:
        light_data = self.blenderObject.data
        if light_data.type not in {"POINT", "SPOT"}:
            logger.error(
                f"Automatic lights must be a Point or Spot light, change {self.blenderObject.name}'s type or"
                f" change it's X-Plane Light Type"
            )
            return
        if parsed_light and not lights_txt.is_automatic_light_compatible(
            self.lightName
        ):
            logger.error(
                f"Light '{self.lightName}' is not compatible with Automatic Lights."
                f" Pick a different light or use 'Library Light, By Name' or 'Library Light, Manual' instead"
            )
            return
        if parsed_light and parsed_light.light_param_def:
            self._fill_automatic_params(parsed_light)
        elif parsed_light:
            self.record_completed = parsed_light.best_overload()
            if "DREF" in self.record_completed.prototype():
                self.record_completed.apply_sw_callback()
        else:
            self._warn_unknown_name()

        if self.record_completed:
            try:
                is_omni = self.record_completed.is_omni()
            except ValueError:
                is_omni = False
            if is_omni and light_data.type == "SPOT":
                logger.error(
                    f"{self.blenderObject.name}'s '{self.lightName}' light will be omnidirectional in X-Plane."
                    f" Use a Point light"
                )
            elif not is_omni and light_data.type == "POINT":
                logger.error(
                    f"{self.blenderObject.name}'s '{self.lightName}' light will be directional in X-Plane."
                    f" Use a Spot light"
                )

    def _automatic_width_and_direction(self, parsed_light: lights_txt.ParsedLight):
        """
        What WIDTH is replaced with (not the final WIDTH or whether the light is omni, other things can change it)
        and the (potentially scaled) light direction, or (0, 0, 0) for omni lights, in X-Plane coords
        """
        light_data = self.blenderObject.data
        if light_data.type == "POINT":
            return 1, Vector((0, 0, 0))
        overload_type = parsed_light.best_overload().overload_type
        is_v12_bb = parsed_light.name in lights_txt.BILLBOARD_USES_SPILL_DXYZ
        if "BILLBOARD" in overload_type and not is_v12_bb:
            width = width_for_billboard(light_data.spot_size)
            # Works for DIR_MAG as well, but we'll probably never have a case for that
            return width, vec_b_to_x(self.get_light_direction_b() * (1 - width))
        if "SPILL" in overload_type or is_v12_bb:
            return width_for_spill(light_data.spot_size), vec_b_to_x(
                self.get_light_direction_b()
            )
        return None, None

    def _fill_automatic_params(self, parsed_light: lights_txt.ParsedLight) -> None:
        light_data = self.blenderObject.data
        settings = light_data.xplane
        width, dxyz_values_x = self._automatic_width_and_direction(parsed_light)
        table = {
            "R": self.color[0],
            "G": self.color[1],
            "B": self.color[2],
            "A": 1,
            "INDEX": settings.param_index,
            "SIZE": settings.param_size,
            "LEGACY_SIZE": 0,  # Another UNUSED - we don't autocorrect with it at all
            "INTENSITY": settings.param_intensity_new,
            "WIDTH": width,
            "FREQ": settings.param_freq,
            "PHASE": settings.param_phase,
            "UNUSED": 0,  # We just shove in something here
            "NEG_ONE": -1,
            "ZERO": 0,
            "ONE": 1,
        }
        if dxyz_values_x is not None:
            table.update(DX=dxyz_values_x[0], DY=dxyz_values_x[1], DZ=dxyz_values_x[2])
        if light_data.type == "SPOT":
            table["DIR_MAG"] = dir_mag_for_billboard(light_data.spot_size)
        elif light_data.type == "POINT":
            table["DIR_MAG"] = 0

        self.params = {
            param: table[param.rstrip("_")] for param in parsed_light.light_param_def
        }
        self.record_completed = parsed_light.best_overload()
        for p_arg in [
            arg
            for arg in self.record_completed
            if not _is_number_ish(arg) and not arg.startswith(("NOOP", "sim"))
        ]:
            self.record_completed.replace_parameterization_argument(
                p_arg, self.params[p_arg]
            )

        # Leaving DXYZ in a record's arguments is okay
        # - It doesn't affect any sw_callbacks (as of 4/19/2020)
        # - We'll be filling in instead of autocorrecting
        if lights_txt.ColumnName.DREF in self.record_completed.prototype():
            self.record_completed.apply_sw_callback()

        try:
            is_omni = self.record_completed.is_omni()
        except (KeyError, TypeError):  # No WIDTH column or no __round__for str
            is_omni = False
        if is_omni:
            try:
                for column in ("DX", "DY", "DZ"):
                    self.record_completed.replace_parameterization_argument(column, 0)
                self.params.update({"DX": 0, "DY": 0, "DZ": 0})
            except ValueError:  # No DX, DY, DZ
                pass

    # X-Plane Light Type | Light Type | parsed_light | light_param_defs | Result
    # -------------------|------------|--------------|------------------|-------
    # LIGHT_SPILL_CUSTOM |"POINT/SPOT"| N/A          | N/A              | Fillout params, write
    # LIGHT_SPILL_CUSTOM | Any others | N/A          | N/A              | Error
    def _collect_spill_custom(self) -> None:
        light_data = self.blenderObject.data
        if light_data.type not in {"POINT", "SPOT"}:
            logger.error(
                f"Spill lights must be a Point or Spot light, change {self.blenderObject.name}'s type or"
                f" change it's X-Plane Light Type"
            )
            return
        p = self.params
        p.r, p.g, p.b = self.color
        p.size = self.size
        if light_data.type == "POINT":
            p.dx, p.dy, p.dz = Vector((0, 0, 0))
            p.width = 1
        else:
            p.dx, p.dy, p.dz = vec_b_to_x(self.get_light_direction_b())
            p.width = width_for_spill(light_data.spot_size)
        p.dataref = self.dataref
