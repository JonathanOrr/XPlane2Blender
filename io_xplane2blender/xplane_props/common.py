"""
Small settings shared by objects, bones, materials, lights and files.
"""

import bpy

from io_xplane2blender.xplane_constants import ANIM_TYPE_HIDE, ANIM_TYPE_SHOW, ANIM_TYPE_TRANSFORM


class XPlaneCustomAttribute(bpy.types.PropertyGroup):
    """An OBJ line typed by hand, for anything the add-on has no setting for"""

    name: bpy.props.StringProperty(name="Name", description="Name")
    value: bpy.props.StringProperty(name="Value", description="Value")
    reset: bpy.props.StringProperty(name="Reset", description="Reset")
    weight: bpy.props.IntProperty(
        name="Weight",
        description="The more weight an attribute has the later it gets written in the OBJ",
        default=0,
        min=0,
    )


class XPlaneDataref(bpy.types.PropertyGroup):
    """A dataref that moves (keyframes) or shows and hides an object or bone"""

    path: bpy.props.StringProperty(name="Dataref Path", description="Dataref Path")
    value: bpy.props.FloatProperty(name="Value", description="Value", default=0.0, precision=6)
    loop: bpy.props.FloatProperty(
        name="Loop Animation Every",
        description="Loop amount of animation, useful for ever increasing Datarefs. A value of 0 will ignore this setting",
        min=0.0,
        precision=3,
    )
    anim_type: bpy.props.EnumProperty(
        name="Dataref Purpose",
        description="Type of animation this Dataref will use",
        default=ANIM_TYPE_TRANSFORM,
        items=[
            (ANIM_TYPE_TRANSFORM, "Transformation", "Transformation"),
            (ANIM_TYPE_SHOW, "Show", "Show"),
            (ANIM_TYPE_HIDE, "Hide", "Hide"),
        ],
    )
    show_hide_v1: bpy.props.FloatProperty(
        name="Value 1", description="Show/Hide value 1", default=0.0, precision=3
    )
    show_hide_v2: bpy.props.FloatProperty(
        name="Value 2", description="Show/Hide value 2", default=0.0, precision=3
    )


class XPlaneAxisDetentRange(bpy.types.PropertyGroup):
    start: bpy.props.FloatProperty(
        name="Start", description="Start value (from Dataref 1) of the detent region", default=0.0, precision=3
    )
    end: bpy.props.FloatProperty(
        name="End", description="End value (from Dataref 1) of the detent region", default=0.0, precision=3
    )
    height: bpy.props.FloatProperty(
        name="Height",
        description="The height (in units of Dataref 2) the user must drag to overcome the detent",
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
            description="If checked values will change the brightness of the _LIT texture for "
            + ("the object" if target == "object" else "objects with this material")
            + ". This overrides the sim's decision about object lighting",
            default=False,
        ),
        "lightLevel_photometric": bpy.props.BoolProperty(
            name="Use Photometric Units",
            description="Use brightness in nts in to change the _LIT texture",
            default=False,
        ),
        "lightLevel_brightness": bpy.props.IntProperty(
            name="Brightness",
            description="The brightness in nts of your _LIT texture at its brightest",
            default=1000,
            min=0,
        ),
        "lightLevel_v1": bpy.props.FloatProperty(
            name="Value 1", description="Value 1 for light level", default=0.0, precision=2
        ),
        "lightLevel_v2": bpy.props.FloatProperty(
            name="Value 2", description="Value 2 for light level", default=1.0, precision=2
        ),
        "lightLevel_dataref": bpy.props.StringProperty(
            name="Dataref",
            description="The dataref is interpreted as a value between v1 and v2. Values outside v1 and v2 are clamped",
        ),
    }


def add_props(cls, props: dict):
    """Adds generated properties to a PropertyGroup before it is registered"""
    cls.__annotations__ = {**cls.__annotations__, **props}
    return cls
