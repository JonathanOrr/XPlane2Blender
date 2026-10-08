"""
What an X-Plane light looks like in Blender.

lights.txt gives every named and parameterized light one or more overloads. Billboards (BILLBOARD_*) are the visible halo
and light nothing, spills (SPILL_*) really illuminate the surroundings, and a light can have both. The importer turns a spill
into a Blender point or spot light, and everything else into a light that is switched off for the render engines, so the
export settings are kept without anything lighting up that X-Plane would not light.

The numbers are for a plausible picture, not a measurement. The exporter writes the light's parameters as they are stored,
it never reads the Blender power of a named, parameterized or spill light.
"""
import math
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from .obj_parser import Light

# A Blender point light of P watts has a radiant intensity of P / (4 pi^2) W/sr, and one watt is 683 lumen
WATTS_PER_CANDELA = 4 * math.pi**2 / 683
# Spills sized in meters carry no intensity, so the power grows with the area they reach
WATTS_PER_SQUARE_METER = 20.0
MIN_WATTS, MAX_WATTS = 0.01, 5000.0
OMNI_WIDTH = 0.9999


@dataclass
class LightLook:
    kind: str = "POINT"  # The Blender light type, POINT or SPOT
    color: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    watts: float = 0.0  # Power with the light switched on, 0 when it does not illuminate
    illuminates: bool = False
    direction: Optional[Tuple[float, float, float]] = None  # X-Plane object space
    spot_size: float = math.pi  # Radians, the full cone angle
    reach: Optional[float] = None  # Meters the light reaches, when its size says


def _number(text) -> float:
    """Numbers in lights.txt and in parameters may carry a 'cd' for candela, or use a decimal comma"""
    text = str(text).strip()
    if text.endswith("cd"):
        text = text[:-2]
    return float(text.replace(",", "."))


def _unit(values: Sequence[float]) -> Optional[Tuple[float, float, float]]:
    length = math.sqrt(sum(v * v for v in values))
    if length < 1e-6:
        return None
    return tuple(v / length for v in values)  # type: ignore[return-value]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _cone(direction, width) -> Tuple[str, Optional[Tuple[float, float, float]], float]:
    """Spills hold the cosine of half their cone angle as the width. Returns the Blender type, direction and cone"""
    unit = _unit(direction) if direction is not None else None
    if unit is None or width is None or width >= OMNI_WIDTH:
        return "POINT", None, math.pi
    half_angle = math.acos(_clamp(width, -1.0, 1.0))
    return "SPOT", unit, _clamp(2 * half_angle, 0.01, math.pi)


def watts_for_candela(candela: float) -> float:
    return _clamp(candela * WATTS_PER_CANDELA, MIN_WATTS, MAX_WATTS)


def watts_for_size(meters: float) -> float:
    return _clamp(WATTS_PER_SQUARE_METER * meters * meters, MIN_WATTS, MAX_WATTS)


_parser_ready = False


def _lights_txt():
    global _parser_ready
    from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as parser

    if not _parser_ready:
        parser.parse_lights_file()
        _parser_ready = True
    return parser


def look_of(light: Light) -> LightLook:
    """How a parsed light should look in Blender. Never raises, an unknown light is a white light that lights nothing"""
    try:
        if light.kind in ("named", "param"):
            return _look_of_lights_txt(light)
        if light.kind == "spill_custom":
            return _look_of_spill_custom(light)
        if light.kind == "custom":
            return LightLook(color=_rgb(light.args[0:3]))
        if light.kind == "vlight":
            return LightLook(color=_rgb(light.args[0:3]))
    except Exception:  # noqa: BLE001 - a light's look is never a reason to fail an import
        pass
    return LightLook()


def _rgb(values) -> Tuple[float, float, float]:
    return tuple(_clamp(_number(v), 0.0, 1.0) for v in values[:3])  # type: ignore[return-value]


def _look_of_spill_custom(light: Light) -> LightLook:
    # r g b a size dx dy dz width dataref
    numbers = [_number(a) for a in light.args[:9]]
    kind, direction, spot = _cone(numbers[5:8], numbers[8])
    return LightLook(
        kind=kind,
        color=_rgb(numbers[0:3]),
        watts=watts_for_size(numbers[4]),
        illuminates=True,
        direction=direction,
        spot_size=spot,
        reach=numbers[4],
    )


def _look_of_lights_txt(light: Light) -> LightLook:
    parser = _lights_txt()
    parsed = parser.get_parsed_light(light.name)
    formal = list(parsed.light_param_def)
    spills = [
        o for o in parsed.overloads if o.overload_type in ("SPILL_HW_DIR", "SPILL_HW_FLA", "SPILL_SW")
    ]
    overload = spills[0] if spills else parsed.best_overload()
    columns = parser.ColumnName

    def value(column) -> Optional[float]:
        try:
            raw = overload[column]
        except (KeyError, ValueError, IndexError):
            return None
        if isinstance(raw, str):
            if raw not in formal:
                return None
            try:
                raw = light.args[formal.index(raw)]
            except IndexError:
                return None
        try:
            return _number(raw)
        except ValueError:
            return None

    color = tuple(
        _clamp(v if v is not None else 1.0, 0.0, 1.0)
        for v in (value(columns.R), value(columns.G), value(columns.B))
    )
    if not spills:
        return LightLook(color=color)  # type: ignore[arg-type]

    size = value(columns.SIZE)
    reach = None
    if size is None:
        watts = watts_for_size(0.5)
    elif light.name in parser.SIZE_AS_INTENSITY:
        watts = watts_for_candela(size)
    else:
        watts = watts_for_size(size)
        reach = size
    direction = (value(columns.DX), value(columns.DY), value(columns.DZ))
    kind, unit, spot = _cone(direction if None not in direction else None, value(columns.WIDTH))
    return LightLook(
        kind=kind,
        color=color,  # type: ignore[arg-type]
        watts=watts,
        illuminates=True,
        direction=unit,
        spot_size=spot,
        reach=reach,
    )
