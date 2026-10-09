"""
Rain, thermal (defrost) and wiper settings for the OBJ header.
"""

from typing import Callable

from ..xplane_constants import PRECISION_OBJ_FLOAT
from ..xplane_helpers import logger
from .xplane_attributes import XPlaneAttributes

NAMES = ("RAIN_scale", "THERMAL_texture", "WIPER_texture", "THERMAL_source2", "WIPER_param")


def _enabled(rain, kind: str):
    return [i for i in range(1, 5) if getattr(rain, f"{kind}_{i}_enabled")]


def _add(attributes: XPlaneAttributes, name: str, value) -> None:
    attr = attributes[name]
    if attr.getValue() is None:
        attr.removeValues()
    attr.addValue(value)


def collect(attributes: XPlaneAttributes, rain, filename: str, relative: Callable[[str], str]) -> None:
    thermal_sources = _enabled(rain, "thermal_source")
    wipers = _enabled(rain, "wiper")

    if thermal_sources and not rain.thermal_texture:
        logger.warn(f"{filename}: Must have Thermal Texture to use Thermal Sources")
    if round(rain.rain_scale, PRECISION_OBJ_FLOAT) < 1.0:
        attributes["RAIN_scale"].setValue(rain.rain_scale)
    if wipers and not rain.wiper_texture:
        logger.warn(f"{filename}: Must have Wiper Texture to use Wipers")

    thermal_path = None
    if rain.thermal_texture and thermal_sources:
        try:
            thermal_path = relative(rain.thermal_texture)
        except (OSError, ValueError):
            pass  # The path's error is logged; the rest of the file still exports
    if thermal_path:
        attributes["THERMAL_texture"].setValue(thermal_path)
        for i in thermal_sources:
            source = getattr(rain, f"thermal_source_{i}")
            if not source.defrost_time:
                defrost_time = 0
                logger.error(f"{filename}'s Thermal Source #{i - 1} has no defrost time")
            else:
                try:
                    defrost_time = float(source.defrost_time)
                except ValueError:
                    defrost_time = source.defrost_time
            if not source.dataref_on_off:
                logger.error(f"{filename}'s Thermal Source #{i - 1} has no on/off dataref")
            _add(attributes, "THERMAL_source2", (i - 1, defrost_time, source.dataref_on_off))

    if rain.wiper_texture and wipers:
        try:
            attributes["WIPER_texture"].setValue(relative(rain.wiper_texture))
        except (OSError, ValueError):
            return  # The path's error is logged; the rest of the file still exports
        for i in range(1, 5):
            # Wipers are numbered from the first, so the list stops at the first one turned off
            if not getattr(rain, f"wiper_{i}_enabled"):
                break
            wiper = getattr(rain, f"wiper_{i}")
            if not wiper.dataref:
                logger.error(f"{filename}'s Wiper #{i} has no dataref")
            if wiper.start >= wiper.end:
                logger.error(
                    f"{filename}'s Wiper #{i} dataref start value ({wiper.start}) is greater than or equal to it's end ({wiper.end})"
                )
            _add(
                attributes,
                "WIPER_param",
                f"{wiper.dataref}    {wiper.start}   {wiper.end}    {wiper.nominal_width}",
            )
