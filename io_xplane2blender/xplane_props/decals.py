"""
Detail texture (decal) settings of an OBJ file. There are two albedo and two normal map decals,
each with the same set of settings, so they are made in a loop.
"""

import bpy

KEYS = (
    ("red_key", "Red Key", "Red channel key"),
    ("green_key", "Green Key", "Green channel key"),
    ("blue_key", "Blue Key", "Blue channel key"),
    ("alpha_key", "Alpha Key", "Alpha channel key"),
    ("modulator", "Modulator Strength", "Modulator strength"),
    ("constant", "Constant Strength", "Constant strength"),
)


def _scales(prefix: str, label: str, what: str) -> dict:
    props = {}
    for suffix, axis in (("scale", ""), ("x_scale", "X "), ("y_scale", "Y ")):
        props[f"{prefix}_{suffix}"] = bpy.props.FloatProperty(
            name=f"{label} {axis}Scale",
            description=f"{axis}scale of the {what}".capitalize(),
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
            description=f"{description} for the {what}",
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
        "texture_modulator": _path("Modulator Texture", "Modulator texture to use for objects on this layer"),
    }
    for i in (1, 2):
        label = f"Detail Texture {i}"
        props[f"file_decal{i}"] = _path(label, "Detail Texture to use for objects on this layer")
        props[f"decal{i}_projected"] = bpy.props.BoolProperty(
            name=f"Make {label} Projected", description="If checked, the detail texture will be projected"
        )
        props.update(_scales(f"decal{i}", label, "detail texture"))
        props.update(_keys(f"rgb_decal{i}", f"RGB {label}", "RGB part of the detail texture"))
        props.update(_keys(f"alpha_decal{i}", f"Alpha {label}", "alpha part of the detail texture"))

        label = f"Normal Map Detail Texture {i}"
        props[f"file_normal_decal{i}"] = _path(label, "Normal map detail texture to use for objects on this layer")
        props[f"normal_decal{i}_projected"] = bpy.props.BoolProperty(
            name=f"Make {label} Projected", description="If checked, the normal map detail texture will be projected"
        )
        props.update(_scales(f"normal_decal{i}", label, "normal map detail texture"))
        props.update(_keys(f"normal_decal{i}", label, "normal map detail texture"))
    return props
