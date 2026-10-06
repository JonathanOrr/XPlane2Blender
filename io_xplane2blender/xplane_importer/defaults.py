"""What datarefs read in X-Plane when an aircraft is parked: used to choose the pose and visibility Blender shows"""
import re
from typing import Tuple

# Datarefs that are not 0 on a parked aircraft. The first matching pattern wins.
_NONZERO_DEFAULTS = (
    (re.compile(r"sim/flightmodel2/gear/deploy_ratio"), 1.0),
    (re.compile(r"sim/aircraft/parts/acf_gear_deploy"), 1.0),
    (re.compile(r"sim/flightmodel/movingparts/gear\d*def"), 1.0),
    (re.compile(r"sim/aircraft/parts/acf_gear_deploy"), 1.0),
    (re.compile(r"sim/flightmodel2/gear/deploy_ratio"), 1.0),
    (re.compile(r"sim/graphics/animation/.*gear_ratio"), 1.0),
    (re.compile(r"sim/aircraft/gear/acf_gear_deploy"), 1.0),
)


def default_value(dataref: str) -> float:
    """The value a dataref has before the sim has changed it"""
    for pattern, value in _NONZERO_DEFAULTS:
        if pattern.search(dataref):
            return value
    return 0.0


def nearest_key_index(values, dataref: str) -> int:
    """The index of the key whose dataref value is closest to the default value"""
    wanted = default_value(dataref)
    best, best_distance = 0, float("inf")
    for index, value in enumerate(values):
        distance = abs(value - wanted)
        if distance < best_distance - 1e-12:
            best, best_distance = index, distance
    return best


def show_hide_visible(kind: str, v1: float, v2: float, dataref: str) -> bool:
    """Whether ANIM_show / ANIM_hide leaves the object visible at the dataref's default value"""
    value = default_value(dataref)
    inside = min(v1, v2) <= value <= max(v1, v2)
    return inside if kind == "show" else not inside
