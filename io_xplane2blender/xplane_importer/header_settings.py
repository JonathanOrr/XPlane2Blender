"""
The OBJ header lines that the add-on has settings for: rain, defrost and wipers, the lit texture's luminance and the
cockpit regions. Kept as extra lines they would not be written: the exporter fills those lines from the settings
"""

import math
from typing import Callable, Set, Tuple

from .obj_parser import ObjFile


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def _shiny_panel(obj: ObjFile) -> bool:
    """A drawn panel (or device) part with a shininess"""
    for run in obj.iter_tris():
        state = dict(run.state)
        cockpit, shiny = state.get("cockpit"), state.get("shiny")
        if (
            cockpit
            and cockpit != ("hud",)
            and shiny
            and state.get("draw") != ("disable",)
        ):
            try:
                if _number(shiny[0]) > 0:
                    return True
            except ValueError:
                pass
    return False


def apply(
    layer, obj: ObjFile, named: Callable[[str], str], warn
) -> Set[Tuple[str, tuple]]:
    """Fills the file's settings from the header. Returns the (directive, args) pairs taken"""
    taken = set()
    if "GLOBAL_specular" not in obj.globals and (
        obj.has_normal_metalness or _shiny_panel(obj)
    ):
        # Without GLOBAL_specular X-Plane's default is 0, where the exporter would write 1 for normal metalness
        # and no shininess for panel parts (Baron screens)
        layer.specular_override, layer.specular = True, 0.0
    for directive, entries in obj.globals.items():
        for args in entries:
            try:
                if _apply_one(layer, directive, args, named):
                    taken.add((directive, tuple(args)))
            except (ValueError, IndexError):
                warn(
                    f"{directive} {' '.join(args)} could not be read, it was kept as an extra line"
                )
    return taken


def _apply_one(layer, directive: str, args, named) -> bool:
    rain = layer.rain
    if directive == "RAIN_scale":
        rain.rain_scale = _number(args[0])
    elif directive == "THERMAL_texture":
        rain.thermal_texture = named(args[0]) or args[0]
    elif directive == "THERMAL_source2":
        number = int(_number(args[0])) + 1
        if not 1 <= number <= 4:
            return False
        setattr(rain, f"thermal_source_{number}_enabled", True)
        source = getattr(rain, f"thermal_source_{number}")
        source.defrost_time, source.dataref_on_off = args[1], args[2]
    elif directive == "WIPER_texture":
        rain.wiper_texture = named(args[0]) or args[0]
    elif directive == "WIPER_param":
        number = next(
            (i for i in range(1, 5) if not getattr(rain, f"wiper_{i}_enabled")), None
        )
        if number is None:
            return False
        wiper = getattr(rain, f"wiper_{number}")
        wiper.dataref = args[0]
        wiper.start, wiper.end, wiper.nominal_width = (_number(a) for a in args[1:4])
        setattr(rain, f"wiper_{number}_enabled", True)
    elif directive == "GLOBAL_specular":
        layer.specular_override = True
        layer.specular = max(0.0, min(1.0, _number(args[0])))
    elif directive == "GLOBAL_luminance":
        layer.luminance_override = True
        layer.luminance = max(1, round(_number(args[0])))
    elif directive == "COCKPIT_REGION":
        return _cockpit_region(layer, [round(_number(a)) for a in args[:4]])
    else:
        return False
    return True


def _cockpit_region(layer, edges) -> bool:
    """COCKPIT_REGION left bottom right top, with sides that are powers of 2 as the add-on stores them"""
    left, bottom, right, top = edges
    count = int(layer.cockpit_regions)
    if count >= 4 or right <= left or top <= bottom:
        return False
    width, height = math.log2(right - left), math.log2(top - bottom)
    if not (width.is_integer() and height.is_integer()):
        return False
    layer.cockpit_regions = str(count + 1)
    region = layer.cockpit_region[count]
    # "top" is the bottom edge, see XPlaneCockpitRegion
    region.left, region.top = left, bottom
    region.width, region.height = int(width), int(height)
    return True
