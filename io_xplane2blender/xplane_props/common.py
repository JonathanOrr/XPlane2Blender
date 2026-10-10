"""
Small settings shared by objects, bones, materials, lights and files.
"""

import bpy

from io_xplane2blender.xplane_constants import ANIM_TYPE_HIDE, ANIM_TYPE_SHOW, ANIM_TYPE_TRANSFORM


class XPlaneCustomAttribute(bpy.types.PropertyGroup):
    """An OBJ line typed by hand, for anything the add-on has no setting for"""

    name: bpy.props.StringProperty(name="Name", description="The OBJ line's keyword, such as ATTR_no_cull")
    value: bpy.props.StringProperty(name="Value", description="The rest of the line, written after the keyword")
    reset: bpy.props.StringProperty(
        name="Reset", description="The line that undoes it, written after the object (such as ATTR_cull for ATTR_no_cull)"
    )
    weight: bpy.props.IntProperty(
        name="Weight",
        description="Lines with a higher order are written later in the OBJ",
        default=0,
        min=0,
    )


class XPlaneDataref(bpy.types.PropertyGroup):
    """A dataref that moves (keyframes) or shows and hides an object or bone"""

    path: bpy.props.StringProperty(
        name="Dataref Path", description="The dataref, such as sim/cockpit2/switches/landing_lights_on, or name[0] for an array"
    )
    value: bpy.props.FloatProperty(name="Value", description="The dataref value of this key", default=0.0, precision=6)
    loop: bpy.props.FloatProperty(
        name="Loop Animation Every",
        description="Repeat the animation every this much of the dataref, for datarefs that keep growing (a turning"
        " propeller). 0: no repeat",
        min=0.0,
        precision=3,
    )
    anim_type: bpy.props.EnumProperty(
        name="Dataref Purpose",
        description="What the dataref does: moves the object, or shows or hides it",
        default=ANIM_TYPE_TRANSFORM,
        items=[
            (ANIM_TYPE_TRANSFORM, "Transformation", "Moves the object, by its keys"),
            (ANIM_TYPE_SHOW, "Show", "Shows the object while the dataref is in a range"),
            (ANIM_TYPE_HIDE, "Hide", "Hides the object while the dataref is in a range"),
        ],
    )
    show_hide_v1: bpy.props.FloatProperty(
        name="Value 1", description="The lowest dataref value of the range", default=0.0, precision=3
    )
    show_hide_v2: bpy.props.FloatProperty(
        name="Value 2", description="The highest dataref value of the range", default=0.0, precision=3
    )


class XPlaneAxisDetentRange(bpy.types.PropertyGroup):
    start: bpy.props.FloatProperty(
        name="Start", description="The dataref value where the lever starts moving freely", default=0.0, precision=3
    )
    end: bpy.props.FloatProperty(
        name="End", description="The dataref value where the lever stops moving freely", default=0.0, precision=3
    )
    height: bpy.props.FloatProperty(
        name="Height",
        description="How far the lever must be lifted to get into this range, in the detent dataref's units",
        default=0.0,
        precision=3,
    )

    def __str__(self):
        return f"({self.start:.3f}, {self.end:.3f}, {self.height:.3f})"


def light_level_props(target: str) -> dict:
    """The light level override settings, which objects and materials both have"""
    return {
        "lightLevel": bpy.props.BoolProperty(
            name="Override Light Level" + (" (This Mesh Only)" if target == "object" else ""),
            description="The night (LIT) texture's brightness follows a dataref, for "
            + ("this object only" if target == "object" else "every object with this material")
            + ", instead of X-Plane's own lighting",
            default=False,
        ),
        "lightLevel_photometric": bpy.props.BoolProperty(
            name="Use Photometric Units",
            description="Give the brightness in nits (cd/m²)",
            default=False,
        ),
        "lightLevel_brightness": bpy.props.IntProperty(
            name="Brightness",
            description="How bright the night (LIT) texture is at its brightest, in nits (cd/m²)",
            default=1000,
            min=0,
        ),
        "lightLevel_v1": bpy.props.FloatProperty(
            name="Value 1", description="The dataref value where the glow is off", default=0.0, precision=2
        ),
        "lightLevel_v2": bpy.props.FloatProperty(
            name="Value 2", description="The dataref value where the glow is full", default=1.0, precision=2
        ),
        "lightLevel_dataref": bpy.props.StringProperty(
            name="Dataref",
            description="The dataref the glow follows, from Off At to Full At. Values beyond them count as the nearest one",
        ),
    }


def add_props(cls, props: dict):
    """Adds generated properties to a PropertyGroup before it is registered"""
    cls.__annotations__ = {**cls.__annotations__, **props}
    return cls
