"""
Decals for the OBJ header: up to two albedo decals, two normal decals and a texture modulator.
A decal is either a library .dcl file or a texture with its keying settings, tiled or projected.
"""

from typing import Callable

from ..xplane_helpers import is_path_decal_lib
from ..xplane_utils.xplane_effective_gloss import get_effective_gloss
from .xplane_attributes import XPlaneAttributes

NAMES = (
    "DECAL_LIB",
    "DECAL_PARAMS",
    "NORMAL_DECAL_PARAMS",
    "DECAL_PARAMS_PROJ",
    "NORMAL_DECAL_PARAMS_PROJ",
    "TEXTURE_MODULATOR",
)


def _keys(options, prefix: str) -> tuple:
    return tuple(
        getattr(options, f"{prefix}_{key}")
        for key in ("red_key", "green_key", "blue_key", "alpha_key", "modulator", "constant")
    )


def _add(attributes: XPlaneAttributes, name: str, value) -> None:
    attr = attributes[name]
    if attr.getValue() is None:
        attr.removeValues()
    attr.addValue(value)


def collect(attributes: XPlaneAttributes, options, relative: Callable[[str], str]) -> None:
    """
    Fills the decal attributes from a file's settings. relative() turns a path into one relative to
    the OBJ and raises OSError or ValueError for a path that can't be written; that decal is skipped.
    """
    for i in (1, 2):
        path = getattr(options, f"file_decal{i}")
        if path:
            try:
                if is_path_decal_lib(path):
                    _add(attributes, "DECAL_LIB", relative(path))
                elif getattr(options, f"decal{i}_projected"):
                    scale = (getattr(options, f"decal{i}_x_scale"), getattr(options, f"decal{i}_y_scale"))
                    keys = _keys(options, f"rgb_decal{i}") + _keys(options, f"alpha_decal{i}")
                    _add(attributes, "DECAL_PARAMS_PROJ", (*scale, 0.0, *keys, relative(path)))
                else:
                    scale = (getattr(options, f"decal{i}_scale"),)
                    keys = _keys(options, f"rgb_decal{i}") + _keys(options, f"alpha_decal{i}")
                    _add(attributes, "DECAL_PARAMS", (*scale, 0.0, *keys, relative(path)))
            except (OSError, ValueError):
                pass

    for i in (1, 2):
        path = getattr(options, f"file_normal_decal{i}")
        if path:
            try:
                keys = _keys(options, f"normal_decal{i}")
                tail = (relative(path), get_effective_gloss(path))
                if getattr(options, f"normal_decal{i}_projected"):
                    scale = (
                        getattr(options, f"normal_decal{i}_x_scale"),
                        getattr(options, f"normal_decal{i}_y_scale"),
                    )
                    _add(attributes, "NORMAL_DECAL_PARAMS_PROJ", (*scale, *keys, *tail))
                else:
                    scale = (getattr(options, f"normal_decal{i}_scale"),)
                    _add(attributes, "NORMAL_DECAL_PARAMS", (*scale, *keys, *tail))
            except (OSError, ValueError):
                pass

    if options.texture_modulator:
        try:
            attributes["TEXTURE_MODULATOR"].setValue(relative(options.texture_modulator))
        except (OSError, ValueError):
            pass
