"""
Scene tab, a file's Detail Textures: up to two albedo and two normal map decals, and a modulator texture.
"""

from io_xplane2blender.xplane_helpers import is_path_decal_lib

from .common import compact_row

KEYS = (
    ("red_key", "Red"),
    ("green_key", "Green"),
    ("blue_key", "Blue"),
    ("alpha_key", "Alpha"),
    ("modulator", "Modulator"),
    ("constant", "Constant"),
)


def _scale_row(layout, layer, prefix: str) -> None:
    row = compact_row(layout)
    row.prop(layer, f"{prefix}_projected", text="Projected", toggle=True)
    if getattr(layer, f"{prefix}_projected"):
        row.prop(layer, f"{prefix}_x_scale", text="X Scale")
        row.prop(layer, f"{prefix}_y_scale", text="Y Scale")
    else:
        row.prop(layer, f"{prefix}_scale", text="Scale")


def _keys_column(layout, layer, prefix: str, title: str) -> None:
    col = layout.column(align=True)
    col.use_property_split = False
    col.label(text=title)
    for key, label in KEYS:
        col.prop(layer, f"{prefix}_{key}", text=label)


def decals_layout(layout, layer) -> None:
    for i in (1, 2):
        box = layout.box()
        path = getattr(layer, f"file_decal{i}")
        box.prop(layer, f"file_decal{i}", text=f"Detail {i}")
        if path and is_path_decal_lib(path):
            box.label(text="A decal library file (.dcl) brings its own settings", icon="INFO")
        elif path:
            _scale_row(box, layer, f"decal{i}")
            row = compact_row(box, align=False)
            _keys_column(row, layer, f"rgb_decal{i}", "Color Keyed By")
            _keys_column(row, layer, f"alpha_decal{i}", "Alpha Keyed By")
    for i in (1, 2):
        box = layout.box()
        box.prop(layer, f"file_normal_decal{i}", text=f"Normal Detail {i}")
        if getattr(layer, f"file_normal_decal{i}"):
            _scale_row(box, layer, f"normal_decal{i}")
            _keys_column(box, layer, f"normal_decal{i}", "Keyed By")
    layout.prop(layer, "texture_modulator", text="Modulator")
    if any(getattr(layer, f"file_{kind}{i}") for kind in ("decal", "normal_decal") for i in (1, 2)):
        row = layout.row(align=True)
        row.operator("xplane.detail_preview", text="Preview In Viewport", icon="SHADING_TEXTURE").remove = False
        row.operator("xplane.detail_preview", text="", icon="X").remove = True
