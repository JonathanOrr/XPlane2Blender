"""
The main class for parsing and interpring the contents of lights.txt.

First parse the file, then get ParsedLights via get_parsed_light and the light name.

These tell you information about the name, any parameters, and its overloads.
Use it's best_overload function to get valuable information about how X-Plane will end up
using this light
"""

import copy
import os
import re
from typing import Dict, List, Tuple

from io_xplane2blender import xplane_constants
from io_xplane2blender.xplane_helpers import logger

# The columns and light lists are read from here by the rest of the add-on
from .xplane_lights_txt_columns import (  # noqa: F401
    BAD_LIGHTS,
    BILLBOARD_USES_SPILL_DXYZ,
    OVERLOAD_TYPES,
    SIZE_AS_INTENSITY,
    ColumnName,
    get_overload_column_info,
)
from .xplane_lights_txt_overload import ParsedLightOverload


class ParsedLight:
    """
    A parsed light represents a light and all its overloads
    from lights.txt

    self.overloads is sorted from most to least confident about what the is supposed to represent
    and which (if any) software_callback should be applied. It is guaranteed.
    This is not applicable to most lights.

    One can tell a light is a parameterized light by if self.light_param_def is empty
    """

    def __init__(self, name: str) -> None:
        self.name = name
        self.overloads: List[ParsedLightOverload] = []
        self.light_param_def: Tuple[str] = tuple()

    def __str__(self) -> str:
        return f"{self.name}: {' '.join(self.light_param_def) if self.light_param_def else ''}, {self.overloads[0]}"

    def best_overload(self) -> ParsedLightOverload:
        if self.name == "radio_obs_flash":
            return self.overloads[1]
        else:
            return self.overloads[0]


def is_automatic_light_compatible(light_name: str) -> bool:
    """
    Returns True if light is compatible, false if not. Throws KeyError if not found in parsed_lights_content
    """
    try:
        get_parsed_light(light_name)
    except KeyError:
        raise
    else:
        return not light_name in {
            # Old v9 lights
            "airplane_landing_size",
            "airplane_landing_flash",
            "airplane_taxi_size",
            "airplane_taxi_flash",
            "airplane_generic_size",
            "airplane_generic_flash",
            "airplane_beacon_size",
            "airplane_strobe_size",
            # Typo
            "full_custom_halo_",
            # Weird test lights
            "apt_light_halo_test",
            "test_lamp0",
            "test_lamp1",
            "test_lamp2",
            "test_lamp3",
            "SW_bb",
            "SW_sp",
            "srgb_test0",
            "srgb_test1",
            "srgb_test2",
            "srgb_test3",
        }


_parsed_lights_txt_content = {}  # type: Dict[str, ParsedLight]


def get_parsed_light(light_name: str) -> ParsedLight:
    """
    Return is a copy from _parsed_lights_txt_content dict.
    Raises KeyError if light not found
    """
    try:
        return copy.deepcopy(_parsed_lights_txt_content[light_name])
    except KeyError as ke:
        raise KeyError(f"{light_name} not found in parsed lights dict") from ke


class LightsTxtFileParsingError(Exception):
    pass


def parse_lights_file():
    """
    Parse the lights.txt file, building the dictionary of parsed lights.

    If already parsed, does nothing. Raises OSError or ValueError
    if file not found or content invalid,
    logger errors and warnings will have been collected
    """
    global _parsed_lights_txt_content
    if _parsed_lights_txt_content:
        return

    num_logger_problems = len(logger.findErrors())
    LIGHTS_FILEPATH = os.path.join(
        xplane_constants.ADDON_RESOURCES_FOLDER, "lights.txt"
    )
    if not os.path.isfile(LIGHTS_FILEPATH):
        logger.error(
            f"lights.txt file was not found in resource folder {LIGHTS_FILEPATH}"
        )
        raise FileNotFoundError

    def is_allowed_param(p: str) -> bool:
        try:
            ColumnName.param_to_canonical_column_name(light_name=None, param_name=p)
        except ValueError:
            return p.startswith(
                (
                    "UNUSED",
                    "NEG_ONE",
                    "ZERO",
                    "ONE",
                    "INDEX",
                    "INTENSITY",
                    "DIR_MAG",
                    "LEGACY_SIZE",
                )
            )
        else:
            return True

    with open(LIGHTS_FILEPATH, "r", encoding="utf-8", errors="replace") as f:
        lines = [
            (line_num, l.strip())
            for line_num, l in enumerate(f.read().splitlines())
            if l.startswith((*OVERLOAD_TYPES, "LIGHT_PARAM_DEF"))
        ]

        for line_num_zero_based, line in lines:
            line_num = (
                line_num_zero_based + 1
            )  # artists expect to see one-based line numbers for fixing errors
            # print(line)
            try:
                comment = line[line.index("#") :]
                line = line[: line.index("#")]
            except ValueError:
                comment = ""

            if comment:
                # print("line", line.split()[1], "comment", comment)
                pass
            try:
                overload_type, light_name, *light_args = line.split()
                if not light_args:
                    raise ValueError
            except ValueError:  # not enough values to unpack
                logger.error(
                    f"{line_num}: Line could not be parsed to '<RECORD_TYPE> <light_name> <params or args list>'"
                )
                continue

            if light_name in BAD_LIGHTS:
                continue

            if not re.match("[A-Za-z0-9_]+", light_name):
                logger.error(
                    f"{line_num}: Light name '{light_name}' must be upper/lower case letters, numbers, or underscores only"
                )
                continue

            def get_parsed_light_of_content_dict(light_name: str) -> ParsedLight:
                try:
                    _parsed_lights_txt_content[light_name]
                except KeyError:
                    _parsed_lights_txt_content[light_name] = ParsedLight(light_name)
                finally:
                    return _parsed_lights_txt_content[light_name]

            if overload_type == "LIGHT_PARAM_DEF":
                parsed_light = get_parsed_light_of_content_dict(light_name)
                if parsed_light.light_param_def:
                    logger.error(
                        f"{line_num}: {light_name} cannot have more than one LIGHT_PARAM_DEF"
                    )
                    continue
                light_argc, *light_argv = light_args
                try:
                    light_argc = int(light_argc)
                except ValueError:
                    logger.error(
                        f"{line_num}: Parameter count for '{light_name}''s LIGHT_PARAM_DEF must be an int, is '{light_argc}'"
                    )
                    continue
                else:
                    if (
                        not light_argc
                        or not light_argv
                        or (light_argc != len(light_argv))
                    ):
                        logger.error(
                            f"{line_num}: '{light_name}''s LIGHT_PARAM_DEF must have a count > 0 and an parameter list of the same length"
                        )
                        continue
                    elif len(set(light_argv)) < len(light_argv):
                        logger.error(
                            f"{line_num}: '{light_name}''s LIGHT_PARAM_DEF has duplicate parameters in it"
                        )
                        continue
                parsed_light.light_param_def = light_argv  # Skip the count
                if parsed_light.light_param_def and any(
                    not is_allowed_param(param)
                    for param in parsed_light.light_param_def
                ):
                    logger.error(
                        f"{line_num}: LIGHT_PARAM_DEF for '{light_name}' contains unknown or invalid parameters: {parsed_light.light_param_def}"
                    )
                    continue
            elif overload_type not in OVERLOAD_TYPES:
                logger.error(
                    f"{line_num}: '{overload_type}' is not a valid OVERLOAD_TYPE."
                )
                continue
            elif len(light_args) < len(get_overload_column_info(overload_type)):
                logger.error(
                    f"{line_num}: Arguments list for '{overload_type} {light_name} {' '.join(light_args)}' is not long enough"
                )
                continue
            elif len(light_args) > len(get_overload_column_info(overload_type)):
                logger.error(
                    f"{line_num}: Arguments list for '{overload_type} {light_name} {' '.join(light_args)}' is too long"
                )
                continue
            else:
                parsed_light = get_parsed_light_of_content_dict(light_name)

                def validate_arguments() -> bool:
                    def validate_parameterization_arg(i, arg) -> bool:
                        try:
                            light_param_def = get_parsed_light(
                                light_name
                            ).light_param_def
                            if (
                                arg in light_param_def
                                and list(
                                    get_overload_column_info(overload_type).values()
                                )[i]
                            ):
                                return True
                        except KeyError:
                            return False
                        else:
                            if (
                                arg == "NULL" or arg == "NOOP" or arg.startswith("sim/")
                            ) and i == len(light_args) - 1:
                                return True
                            elif re.match(r"-?\d+(\.\d+)?", arg):
                                return True
                            else:
                                return False

                    prev_logger_errors = len(logger.findErrors())
                    for i, arg in enumerate(light_args):
                        if not validate_parameterization_arg(i, arg):
                            logger.error(
                                f"{line_num}, '{light_name}', arg #{i+1}: ('{arg}')"
                                f" is not a correctly formatted number or is invalid"
                            )
                            continue

                    return not (len(logger.findErrors()) - prev_logger_errors)

                if not validate_arguments():
                    continue

                def tryfloat(s: str) -> float:
                    try:
                        return float(s)
                    except ValueError:
                        return s

                parsed_light.overloads.append(
                    ParsedLightOverload(
                        overload_type=overload_type,
                        name=light_name,
                        arguments=list(map(tryfloat, light_args)),
                    )
                )
                # This is a heuristic/careful reading of X-Plane's light system
                # of what is most likely to give us
                # the correct direction to autocorrect
                rankings = [
                    "SPILL_HW_DIR",  # Most trustworthy
                    "SPILL_HW_FLA",
                    "SPILL_SW",
                    "BILLBOARD_HW",
                    "BILLBOARD_SW",  # Least trustworthy
                    "SPILL_GND",  # Ignored by autocorrector, ranked last
                    "SPILL_GND_REV",  # Ignored by autocorrector, ranked last
                ]

                # Semantically speaking, overloads[0] must ALWAYS be the most trustworthy
                parsed_light.overloads.sort(
                    key=lambda l: rankings.index(l.overload_type)
                )

    for light_name, pl in _parsed_lights_txt_content.items():
        if not pl.overloads:
            logger.error(
                f"Ignoring '{light_name}': Found LIGHT_PARAM_DEF but no valid overloads"
            )
            continue

    _parsed_lights_txt_content = {
        light_name: pl
        for light_name, pl in _parsed_lights_txt_content.items()
        if pl.overloads
    }

    if not _parsed_lights_txt_content:
        logger.error("lights.txt had no valid light records in it")
    if len(logger.findErrors()) - num_logger_problems:
        raise LightsTxtFileParsingError
