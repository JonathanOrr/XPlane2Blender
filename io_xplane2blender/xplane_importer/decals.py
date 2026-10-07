"""
An OBJ's detail textures (decals) and texture modulator, put into the file's Detail Textures settings so they can be
edited and previewed. They are read in the shape the exporter writes them; anything else (a third decal, a dither
the settings can't hold, the old DECAL forms) stays an extra OBJ line, written back as it was.
"""

from typing import Callable, List, Optional, Set

from .obj_records import ObjFile

KEYS = ("red_key", "green_key", "blue_key", "alpha_key", "modulator", "constant")
DIRECTIVES = (
    "DECAL_LIB",
    "DECAL_PARAMS",
    "DECAL_PARAMS_PROJ",
    "NORMAL_DECAL_PARAMS",
    "NORMAL_DECAL_PARAMS_PROJ",
)


def _numbers(args: List[str]) -> Optional[List[float]]:
    try:
        return [float(a) for a in args]
    except ValueError:
        return None


def _set_keys(layer, prefix: str, keys: List[float]) -> None:
    for name, value in zip(KEYS, keys):
        setattr(layer, f"{prefix}_{name}", value)


def _color_decal(
    layer, i: int, directive: str, args: List[str], path: Callable[[str], str]
) -> bool:
    if directive == "DECAL_LIB":
        if len(args) != 1:
            return False
        setattr(layer, f"file_decal{i}", path(args[0]))
        return True
    projected = directive == "DECAL_PARAMS_PROJ"
    count = 2 if projected else 1
    numbers = _numbers(args[: count + 13])
    # scale(s), dither, 6 color keys, 6 alpha keys, texture. The settings have no dither, the exporter writes 0
    if len(args) != count + 14 or numbers is None or numbers[count] != 0:
        return False
    setattr(layer, f"decal{i}_projected", projected)
    if projected:
        setattr(layer, f"decal{i}_x_scale", numbers[0])
        setattr(layer, f"decal{i}_y_scale", numbers[1])
    else:
        setattr(layer, f"decal{i}_scale", numbers[0])
    _set_keys(layer, f"rgb_decal{i}", numbers[count + 1 : count + 7])
    _set_keys(layer, f"alpha_decal{i}", numbers[count + 7 : count + 13])
    setattr(layer, f"file_decal{i}", path(args[-1]))
    return True


def _normal_decal(
    layer, i: int, directive: str, args: List[str], path: Callable[[str], str]
) -> bool:
    projected = directive == "NORMAL_DECAL_PARAMS_PROJ"
    count = 2 if projected else 1
    # scale(s), 6 keys, texture, gloss. The gloss is worked out from the texture again on export
    numbers = _numbers(args[: count + 6])
    if len(args) != count + 8 or numbers is None:
        return False
    setattr(layer, f"normal_decal{i}_projected", projected)
    if projected:
        setattr(layer, f"normal_decal{i}_x_scale", numbers[0])
        setattr(layer, f"normal_decal{i}_y_scale", numbers[1])
    else:
        setattr(layer, f"normal_decal{i}_scale", numbers[0])
    _set_keys(layer, f"normal_decal{i}", numbers[count : count + 6])
    setattr(layer, f"file_normal_decal{i}", path(args[-2]))
    return True


def apply_decals(layer, obj: ObjFile, path: Callable[[str], str]) -> Set[tuple]:
    """
    Fills the file's detail texture settings from the OBJ. path() turns an OBJ texture path into the one to store.
    Returns the (directive, line) pairs that were taken, so they are not also kept as extra lines
    """
    taken = set()
    color, normal = 0, 0
    for directive in DIRECTIVES:
        for args in obj.globals.get(directive, []):
            if directive.startswith("NORMAL"):
                if normal < 2 and _normal_decal(
                    layer, normal + 1, directive, args, path
                ):
                    normal += 1
                    taken.add((directive, tuple(args)))
            elif color < 2 and _color_decal(layer, color + 1, directive, args, path):
                color += 1
                taken.add((directive, tuple(args)))
    if obj.texture_modulator:
        layer.texture_modulator = path(obj.texture_modulator[0])
    return taken
