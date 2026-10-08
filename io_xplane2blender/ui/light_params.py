"""
Object tab, Light card, Library Light, Manual: the parameters as settings (a color, a direction, a
size) instead of one line of text to type. Nothing is stored here: each setting reads and writes its value in the
light's own line of parameters, so that line stays what the exporter writes and the text can still be edited by hand.
"""

import math
from typing import Dict, List, Tuple

import bpy

from io_xplane2blender import xplane_light_tools as tools
from io_xplane2blender.xplane_light_sync import links
from io_xplane2blender.xplane_utils import xplane_light_params as lp

from .common import wrapped


def _formal(light: bpy.types.Light) -> List[str]:
    return tools.formal_params(light.xplane.name)


def _values(light: bpy.types.Light) -> Dict[str, float]:
    return lp.values_of(light.xplane.params, _formal(light))


def _change(light: bpy.types.Light, changes: Dict[str, float]) -> None:
    formal = _formal(light)
    if not formal:
        return
    line = lp.update_line(light.xplane.params, formal, changes)
    if line != light.xplane.params:
        light.xplane.params = line


def _number(kind, parameter: str, name: str, description: str, **options):
    """A setting that is the value of one parameter of the line"""
    integer = kind is bpy.props.IntProperty

    def get(self):
        value = _values(self.id_data).get(parameter, 0.0)
        return int(round(value)) if integer else value

    def set(self, value):
        _change(self.id_data, {parameter: float(value)})

    return kind(name=name, description=description, get=get, set=set, **options)


def _triple(names: Tuple[str, str, str], **options):
    """A setting that is the value of three parameters of the line in a row"""

    def get(self):
        values = _values(self.id_data)
        return tuple(values.get(name, 0.0) for name in names)

    def set(self, value):
        _change(self.id_data, dict(zip(names, map(float, value))))

    return bpy.props.FloatVectorProperty(size=3, get=get, set=set, **options)


def _cone_angle():
    """The cone of a typed light as an angle, which is what Blender's Spot Size is, instead of the cosine of half of
    it that lights.txt has as WIDTH"""

    def get(self):
        data = self.id_data
        style = links.cone_style(data.xplane.name)
        width = lp.values_of(data.xplane.params, _formal(data)).get("WIDTH", 1.0)
        return links.spot_size_of(style, width) if style else math.pi

    def set(self, value):
        data = self.id_data
        style = links.cone_style(data.xplane.name)
        if style:
            links.Cone().set_stored(data, links.width_of(style, value))

    return bpy.props.FloatProperty(
        name="Cone Angle",
        description="How wide the light shines, as Blender's Spot Size. It is written as the cosine of half of it",
        subtype="ANGLE",
        unit="ROTATION",
        min=links.MIN_CONE,
        max=links.MAX_CONE,
        get=get,
        set=set,
    )


class XPlaneLightParams(bpy.types.PropertyGroup):
    """bpy.types.Light.xplane_params: the values of a library light's parameter line, which stores them"""

    color: _triple(
        ("R", "G", "B"),
        name="Color",
        description="The light's color",
        subtype="COLOR",
        min=0.0,
        max=1.0,
    )
    direction: _triple(
        ("DX", "DY", "DZ"),
        name="Direction",
        description="The way the light points, in X-Plane's axes: X to the right, Y up, Z toward the back",
        subtype="XYZ",
        precision=3,
    )
    alpha: _number(
        bpy.props.FloatProperty,
        "A",
        "Alpha",
        "How opaque the light is",
        min=0.0,
        max=1.0,
        precision=3,
    )
    size: _number(
        bpy.props.FloatProperty,
        "SIZE",
        "Light Size",
        "Spill size uses meters; billboard size uses arbitrary scales - bigger is brighter",
        min=0.0,
        precision=3,
    )
    intensity: _number(
        bpy.props.FloatProperty,
        "INTENSITY",
        "Intensity",
        "Total light output in a specific direction, in candela",
        min=0.0,
        precision=1,
    )
    cone_angle: _cone_angle()
    width: _number(
        bpy.props.FloatProperty,
        "WIDTH",
        "Width",
        "The cone of the light: the cosine of half its angle, 1 for a light that shines all around",
        precision=3,
    )
    index: _number(
        bpy.props.IntProperty,
        "INDEX",
        "Dataref Index",
        "Index in the light's associated array dataref",
        min=0,
        soft_max=127,
    )
    freq: _number(
        bpy.props.FloatProperty,
        "FREQ",
        "Flash Frequency",
        "The number of light flashes per second",
        min=0.0,
    )
    phase: _number(
        bpy.props.FloatProperty,
        "PHASE",
        "Phase Offset",
        "Phase offset in seconds of light (so it can make flashing lights that don't flash at the same time)",
        min=0.0,
    )
    dir_mag: _number(
        bpy.props.FloatProperty,
        "DIR_MAG",
        "Direction Strength",
        "How strongly the light shines one way: 0 is all around",
        precision=3,
    )


# The settings of a parameter that is one value, by its name in lights.txt
SINGLES = {
    "A": "alpha",
    "SIZE": "size",
    "INTENSITY": "intensity",
    "WIDTH": "width",
    "INDEX": "index",
    "FREQ": "freq",
    "PHASE": "phase",
    "DIR_MAG": "dir_mag",
}


def _directional_cone(data: bpy.types.Light) -> bool:
    """Whether the typed WIDTH of the light is a cone that can be shown as an angle"""
    if links.cone_style(data.xplane.name) is None:
        return False
    return (
        lp.values_of(data.xplane.params, _formal(data)).get("WIDTH", 1.0)
        < links.OMNI_WIDTH
    )


def parameters_layout(layout, data: bpy.types.Light) -> None:
    """One setting for each parameter the light takes, and the line they make as text"""
    x = data.xplane
    names = [lp.canonical(n) for n in tools.formal_params(x.name)]
    col = layout.column()
    if names:
        typed = data.xplane_params
        i = 0
        while i < len(names):
            name = names[i]
            if lp.is_fixed(name):
                i += 1
            elif names[i : i + 3] == ["R", "G", "B"]:
                col.prop(typed, "color")
                i += 3
            elif names[i : i + 3] == ["DX", "DY", "DZ"]:
                if data.type == "SPOT":
                    # A spot light's rotation is the direction: the exporter turns the typed one to match
                    wrapped(col, "Direction: rotate the Blender light", "INFO")
                else:
                    col.prop(typed, "direction")
                i += 3
            else:
                if name == "WIDTH" and _directional_cone(data):
                    col.prop(typed, "cone_angle")
                elif name in SINGLES:
                    col.prop(typed, SINGLES[name])
                i += 1
    if names:
        wrapped(
            col,
            "Color, Cone Angle, Power and Custom Distance of the Blender light follow these values, and the other way round",
            "LINKED",
        )
    col.prop(x, "params", text="As Text")


classes = (XPlaneLightParams,)
