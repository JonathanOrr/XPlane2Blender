"""
Detail texture (decal) settings of an OBJ file. There are two albedo and two normal map decals,
each with the same set of settings, so they are made in a loop.
"""

import bpy

KEYS = (
    ("red_key", "Red Key", "How much the day texture's red adds to the strength"),
    ("green_key", "Green Key", "How much the day texture's green adds to the strength"),
    ("blue_key", "Blue Key", "How much the day texture's blue adds to the strength"),
    ("alpha_key", "Alpha Key", "How much the day texture's alpha adds to the strength"),
    ("modulator", "Modulator Strength", "How much the modulator texture adds to the strength"),
    ("constant", "Constant Strength", "The strength added everywhere"),
)


def _scales(prefix: str, label: str, what: str) -> dict:
    props = {}
    for suffix, axis in (("scale", ""), ("x_scale", "X "), ("y_scale", "Y ")):
        props[f"{prefix}_{suffix}"] = bpy.props.FloatProperty(
            name=f"{label} {axis}Scale",
            description=f"How many times the {what} repeats across the day texture" + (f", along {axis.strip()}" if axis else ""),
            min=0.0,
            step=0.1,
            precision=2,
            default=1.0,
        )
    return props


def _keys(prefix: str, label: str, what: str) -> dict:
    return {
        f"{prefix}_{key}": bpy.props.FloatProperty(
            name=f"{label} {name}",
            description=f"{description}, for the {what}",
            step=0.01,
            precision=2,
            default=0.0,
        )
        for key, name, description in KEYS
    }


def _path(name: str, description: str):
    return bpy.props.StringProperty(subtype="FILE_PATH", name=name, description=description)


def decal_props() -> dict:
    props = {
        "texture_modulator": _path(
            "Modulator Texture", "A texture whose red sets, part by part, how strongly the detail textures show"
        ),
    }
    for i in (1, 2):
        label = f"Detail Texture {i}"
        props[f"file_decal{i}"] = _path(label, "A detail texture, repeated over the day texture for fine detail up close")
        props[f"decal{i}_projected"] = bpy.props.BoolProperty(
            name=f"Make {label} Projected", description="Project the detail texture by position instead of the UVs"
        )
        props.update(_scales(f"decal{i}", label, "detail texture"))
        props.update(_keys(f"rgb_decal{i}", f"RGB {label}", "RGB part of the detail texture"))
        props.update(_keys(f"alpha_decal{i}", f"Alpha {label}", "alpha part of the detail texture"))

        label = f"Normal Map Detail Texture {i}"
        props[f"file_normal_decal{i}"] = _path(label, "A normal map detail texture, repeated over the normal map")
        props[f"normal_decal{i}_projected"] = bpy.props.BoolProperty(
            name=f"Make {label} Projected", description="Project the normal map detail texture by position instead of the UVs"
        )
        props.update(_scales(f"normal_decal{i}", label, "normal map detail texture"))
        props.update(_keys(f"normal_decal{i}", label, "normal map detail texture"))
    return props
