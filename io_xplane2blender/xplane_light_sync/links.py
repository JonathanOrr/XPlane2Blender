"""
The numbers an X-Plane light and its Blender light have in common. Each is one number with two homes: where X-Plane
keeps it (a setting of the card, or a word of the typed parameters) and where Blender has it (Power, Custom Distance,
Spot Size, Color). They are kept equal, so either can be changed:

- Intensity (candela) and Power (watts), while the light is on, that is above 0 watts
- Reach (meters, which only spills have) and Custom Distance, while it is switched on
- Cone (the typed WIDTH) and Spot Size, for typed lights only (the others are always written from the Blender light)
- Color (the typed R G B) and Color, for typed lights only

Rotation needs no link: the Blender light's rotation is the direction X-Plane gets, for every kind of light.
"""

import functools
import math
from typing import Any, List, Optional

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_display_sizes as display_sizes
from io_xplane2blender import xplane_light_tools as tools
from io_xplane2blender.xplane_importer.lights import WATTS_PER_CANDELA
from io_xplane2blender.xplane_types.xplane_light_collect import (
    width_for_billboard,
)
from io_xplane2blender.xplane_utils import xplane_light_params as typed
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as lights_txt

MIN_INTENSITY, MAX_INTENSITY = 0.01, 1000000.0
MIN_CONE, MAX_CONE = math.radians(1.0), math.pi
# A typed WIDTH from here on is a light that shines all around, which is a Point light in Blender
OMNI_WIDTH = 0.9999
STRENGTH = "xplane_strength"


def strength(data: bpy.types.Light) -> float:
    """What the last preview multiplied the power by, so that it can be taken out again"""
    try:
        return float(data.get(STRENGTH, 1.0)) or 1.0
    except (TypeError, ValueError):
        return 1.0


def differs(a: Any, b: Any) -> bool:
    if isinstance(a, (tuple, list)):
        return any(differs(x, y) for x, y in zip(a, b)) or len(a) != len(b)
    if isinstance(a, bool) or isinstance(b, bool):
        return a != b
    return abs(a - b) > 1e-6 + 1e-6 * abs(b)


class Link:
    """One number shared by the X-Plane light and the Blender light"""

    quantity = ""

    def available(self, data: bpy.types.Light) -> bool:
        raise NotImplementedError

    def stored(self, data: bpy.types.Light) -> Any:
        """The number where X-Plane keeps it"""
        raise NotImplementedError

    def set_stored(self, data: bpy.types.Light, value: Any) -> None:
        raise NotImplementedError

    def blender(self, data: bpy.types.Light) -> Any:
        """The Blender side, something to compare with what it was before"""
        raise NotImplementedError

    def set_blender(self, data: bpy.types.Light) -> None:
        """Makes the Blender side say what X-Plane has"""
        raise NotImplementedError

    def from_blender(self, data: bpy.types.Light) -> Any:
        """What X-Plane should have, to match the Blender side"""
        raise NotImplementedError

    def is_set(self, data: bpy.types.Light) -> bool:
        """Whether the Blender side says something: a light that is off has no power to take in"""
        return True

    def adoptable(self, data: bpy.types.Light) -> bool:
        """Whether a new typed light starts from the Blender side of this number"""
        return self.available(data)

    def reaction(self, data: bpy.types.Light, before: Any, now: Any) -> str:
        """What a change of the Blender side from before to now means: 'pull' it into X-Plane, 'push' X-Plane out, or
        nothing"""
        return "pull" if differs(now, before) else ""


def _typed(data: bpy.types.Light):
    """(the formal parameter names of a typed light, its values by name), or ([], {}) for other kinds"""
    x = data.xplane
    if x.type != C.LIGHT_PARAM:
        return [], {}
    formal = tools.formal_params(x.name)
    return formal, typed.values_of(x.params, formal) if formal else {}


def _set_typed(data: bpy.types.Light, changes) -> None:
    x = data.xplane
    formal = tools.formal_params(x.name)
    line = typed.update_line(x.params, formal, changes)
    if line != x.params:
        x.params = line


class Intensity(Link):
    quantity = "intensity"

    def available(self, data):
        x = data.xplane
        if x.type not in (C.LIGHT_AUTOMATIC, C.LIGHT_PARAM):
            return False
        return "INTENSITY" in [typed.canonical(p) for p in tools.formal_params(x.name)]

    def stored(self, data):
        if data.xplane.type == C.LIGHT_PARAM:
            return _typed(data)[1].get("INTENSITY", MIN_INTENSITY)
        return data.xplane.param_intensity_new

    def set_stored(self, data, value):
        value = min(max(value, MIN_INTENSITY), MAX_INTENSITY)
        if data.xplane.type == C.LIGHT_PARAM:
            _set_typed(data, {"INTENSITY": value})
        elif differs(data.xplane.param_intensity_new, value):
            data.xplane.param_intensity_new = value

    def blender(self, data):
        return data.energy

    def is_set(self, data):
        return data.energy > 0.0

    def set_blender(self, data):
        if data.energy > 0.0:
            data.energy = self.stored(data) * WATTS_PER_CANDELA * strength(data)

    def from_blender(self, data):
        return data.energy / (WATTS_PER_CANDELA * strength(data))

    def reaction(self, data, before, now):
        return "pull" if now > 0.0 and differs(now, before) else ""


@functools.lru_cache(maxsize=1024)
def _has_reach(name: str) -> bool:
    """Whether a lights.txt light is a spill sized in meters, the only kind X-Plane gives a reach"""
    if "SIZE" not in [typed.canonical(p) for p in tools.formal_params(name)]:
        return False
    from io_xplane2blender.xplane_importer.lights import look_of
    from io_xplane2blender.xplane_importer.obj_parser import Light

    sample = {
        "R": "1",
        "G": "1",
        "B": "1",
        "A": "1",
        "SIZE": "2.5",
        "INTENSITY": "500cd",
        "WIDTH": "0.5",
        "DY": "-1",
    }
    args = [sample.get(typed.canonical(p), "0") for p in tools.formal_params(name)]
    return look_of(Light("param", (0.0, 0.0, 0.0), name, args)).reach is not None


class Reach(Link):
    quantity = "reach"

    def available(self, data):
        x = data.xplane
        if x.type == C.LIGHT_SPILL_CUSTOM:
            return True
        if x.type not in (C.LIGHT_AUTOMATIC, C.LIGHT_PARAM):
            return False
        return _has_reach(x.name.strip())

    def stored(self, data):
        x = data.xplane
        if x.type == C.LIGHT_SPILL_CUSTOM:
            return x.size
        if x.type == C.LIGHT_PARAM:
            return _typed(data)[1].get("SIZE", C.LIGHT_PARAM_SIZE_MIN)
        return x.param_size

    def set_stored(self, data, value):
        x = data.xplane
        value = max(value, C.LIGHT_PARAM_SIZE_MIN)
        if x.type == C.LIGHT_SPILL_CUSTOM:
            if differs(x.size, value):
                x.size = value
        elif x.type == C.LIGHT_PARAM:
            _set_typed(data, {"SIZE": value})
        elif differs(x.param_size, value):
            x.param_size = value

    def blender(self, data):
        return (bool(data.use_custom_distance), data.cutoff_distance)

    def is_set(self, data):
        return bool(data.use_custom_distance)

    def set_blender(self, data):
        reach = max(self.stored(data), C.LIGHT_PARAM_SIZE_MIN)
        if not data.use_custom_distance:
            data.use_custom_distance = True
        if differs(data.cutoff_distance, reach):
            data.cutoff_distance = reach
        # The distance is the reach, which is what Tidy would make it too
        data[display_sizes.TIDIED] = True

    def from_blender(self, data):
        return data.cutoff_distance

    def reaction(self, data, before, now):
        if not now[0]:
            return ""
        if not before[0]:
            # Just switched on: the reach is what it was, so it is Blender's distance that changes
            return "push"
        return "pull" if differs(now[1], before[1]) else ""


def cone_style(name: str) -> Optional[str]:
    """How the typed WIDTH of a light follows its cone: 'spill' (the cosine of half the angle) or 'billboard' (the
    older way, which also scales the direction), or None for a light with no WIDTH"""
    formal = [typed.canonical(p) for p in tools.formal_params(name)]
    if "WIDTH" not in formal:
        return None
    parsed = tools.parsed_light(name)
    try:
        overload = parsed.best_overload().overload_type
    except ValueError:
        return None
    if name in lights_txt.BILLBOARD_USES_SPILL_DXYZ or "SPILL" in overload:
        return "spill"
    return "billboard" if "BILLBOARD" in overload else None


def width_of(style: str, spot_size: float) -> float:
    if style == "spill":
        return max(0.0, math.cos(spot_size / 2.0))
    return width_for_billboard(spot_size)


def spot_size_of(style: str, width: float) -> float:
    cosine = width if style == "spill" else width / (width - 1.0)
    return min(max(2.0 * math.acos(min(max(cosine, -1.0), 1.0)), MIN_CONE), MAX_CONE)


class Cone(Link):
    quantity = "cone"

    def adoptable(self, data):
        return (
            data.xplane.type == C.LIGHT_PARAM
            and data.type == "SPOT"
            and cone_style(data.xplane.name) is not None
        )

    def available(self, data):
        # A typed light that shines all around has no cone: its Blender light is a Point light
        return self.adoptable(data) and _typed(data)[1].get("WIDTH", 1.0) < OMNI_WIDTH

    def stored(self, data):
        return _typed(data)[1].get("WIDTH", 1.0)

    def set_stored(self, data, width):
        style = cone_style(data.xplane.name)
        changes = {"WIDTH": width}
        values = _typed(data)[1]
        if style == "billboard" and all(k in values for k in ("DX", "DY", "DZ")):
            # The direction of these lights is as long as one minus the width: it turns with the cone
            old = Vector((values["DX"], values["DY"], values["DZ"]))
            scale = 1.0 - values["WIDTH"]
            if abs(scale) > 1e-6 and old.length > 1e-9:
                new = old / scale * (1.0 - width)
                changes.update(DX=new.x, DY=new.y, DZ=new.z)
        _set_typed(data, changes)

    def blender(self, data):
        return data.spot_size

    def set_blender(self, data):
        spot = spot_size_of(cone_style(data.xplane.name), self.stored(data))
        if differs(data.spot_size, spot):
            data.spot_size = spot

    def from_blender(self, data):
        return width_of(cone_style(data.xplane.name), data.spot_size)


class Color(Link):
    quantity = "color"

    def available(self, data):
        x = data.xplane
        if x.type != C.LIGHT_PARAM:
            return False
        formal = [typed.canonical(p) for p in tools.formal_params(x.name)]
        return all(c in formal for c in ("R", "G", "B"))

    def stored(self, data):
        values = _typed(data)[1]
        return tuple(values.get(c, 1.0) for c in ("R", "G", "B"))

    def set_stored(self, data, rgb):
        _set_typed(data, dict(zip(("R", "G", "B"), rgb)))

    def blender(self, data):
        return tuple(data.color)

    def set_blender(self, data):
        rgb = self.stored(data)
        # The color picker holds 0 to 1, typed colors can be outside it, and those are left as they are
        if all(0.0 <= c <= 1.0 for c in rgb) and differs(tuple(data.color), rgb):
            data.color = rgb

    def from_blender(self, data):
        return tuple(data.color)


def adopt_direction(data: bpy.types.Light, obj: bpy.types.Object) -> None:
    """Types the direction a Spot light shines into a typed light that has one. It is only a start: the exporter turns
    the typed direction to wherever the Blender light points, whatever frame the light is in
    """
    formal = [typed.canonical(p) for p in tools.formal_params(data.xplane.name)]
    if (
        data.xplane.type != C.LIGHT_PARAM
        or data.type != "SPOT"
        or not all(c in formal for c in ("DX", "DY", "DZ"))
    ):
        return
    shine = obj.matrix_world.to_quaternion() @ Vector((0.0, 0.0, -1.0))
    x, y, z = shine.x, shine.z, -shine.y  # X-Plane is y up
    scale = 1.0
    if cone_style(data.xplane.name) == "billboard":
        scale = 1.0 - _typed(data)[1].get("WIDTH", 0.0)
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    _set_typed(
        data,
        {"DX": x / length * scale, "DY": y / length * scale, "DZ": z / length * scale},
    )


LINKS = (Intensity(), Reach(), Cone(), Color())


def links_of(data: bpy.types.Light) -> List[Link]:
    """The numbers this light shares with its Blender light, for the kind of light it is"""
    if data.xplane.type == C.LIGHT_NON_EXPORTING:
        return []
    return [link for link in LINKS if link.available(data)]
