"""
A parser for X-Plane OBJ8 files (versions 800 to 1200) that has no dependency on Blender.

parse_obj() returns an ObjFile: the vertex and index tables, the global (header) directives,
and a tree of animation nodes holding every drawable thing (triangle runs, lights, emitters,
magnets...) together with the attribute state that was active when it was drawn.
Anything it does not understand is kept in ObjFile.unknown, never silently dropped.
"""

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

Vec3 = Tuple[float, float, float]
# The attribute state is a mapping of a state key ("draw", "blend", "manip"...) to a tuple of values.
# It is frozen into a hashable tuple so that runs with the same state can be grouped.
FrozenState = Tuple[Tuple[str, Any], ...]


class ObjParseError(Exception):
    pass


@dataclass
class AnimOp:
    """One ANIM_trans or ANIM_rotate. It is static when it has no dataref."""

    kind: str  # "trans" or "rotate"
    dataref: str = ""
    axis: Vec3 = (0.0, 0.0, 0.0)  # rotate only
    # For trans: (value, (x, y, z)). For rotate: (value, (angle,))
    keys: List[Tuple[float, Tuple[float, ...]]] = field(default_factory=list)
    loop: float = 0.0

    @property
    def is_static(self) -> bool:
        if not self.dataref or self.dataref in ("none", "no_ref"):
            return True
        # A dataref where every key is identical does nothing
        first = self.keys[0][1] if self.keys else None
        return len(self.keys) < 2 or all(k[1] == first for k in self.keys)

    @property
    def static_value(self) -> Tuple[float, ...]:
        """The vector or angle used when the op is static"""
        return (
            self.keys[0][1]
            if self.keys
            else ((0.0, 0.0, 0.0) if self.kind == "trans" else (0.0,))
        )


@dataclass
class Visibility:
    kind: str  # "show" or "hide"
    v1: float
    v2: float
    dataref: str
    loop: float = 0.0


@dataclass
class TrisRun:
    offset: int
    count: int
    state: FrozenState = ()
    lod: Optional[Tuple[float, float]] = None


@dataclass
class Light:
    kind: str  # "named", "custom", "param", "spill_custom", "vlight"
    position: Vec3
    name: str = ""
    args: List[str] = field(default_factory=list)
    state: FrozenState = ()
    lod: Optional[Tuple[float, float]] = None


@dataclass
class Extra:
    """Magnets, emitters, particle systems and other placed items"""

    kind: str
    args: List[str]
    state: FrozenState = ()
    lod: Optional[Tuple[float, float]] = None


@dataclass
class AnimNode:
    ops: List[AnimOp] = field(default_factory=list)
    visibility: List[Visibility] = field(default_factory=list)
    children: List[Union["AnimNode", TrisRun, Light, Extra]] = field(
        default_factory=list
    )
    comment: str = (
        ""  # The last comment line seen before the block, often a useful name
    )
    lod: Optional[Tuple[float, float]] = None


@dataclass
class ObjFile:
    path: str = ""
    version: int = 800
    # TEXTURE, TEXTURE_LIT, TEXTURE_NORMAL, plus TEXTURE_MAP entries (kind -> path)
    texture: str = ""
    texture_lit: str = ""
    texture_normal: str = ""
    texture_maps: Dict[str, str] = field(default_factory=dict)
    texture_draped: str = ""
    texture_modulator: List[str] = field(default_factory=list)
    # GLOBAL_*, BLEND_GLASS, NORMAL_METALNESS and similar: directive -> list of argument lists
    globals: Dict[str, List[List[str]]] = field(default_factory=dict)
    # The VT table as an (N, 8) array of x y z nx ny nz s t, and the IDX table as one flat array
    vertices: np.ndarray = field(default_factory=lambda: np.zeros((0, 8)))
    indices: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    root: AnimNode = field(default_factory=AnimNode)
    lods: List[Tuple[float, float]] = field(default_factory=list)
    unknown: Dict[str, int] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    point_counts: Tuple[int, int, int, int] = (0, 0, 0, 0)
    vlights: List[Tuple[float, ...]] = field(default_factory=list)

    @property
    def has_normal_metalness(self) -> bool:
        return "NORMAL_METALNESS" in self.globals

    def iter_tris(self):
        """Yields every TrisRun in the tree in file order"""
        stack = [iter(self.root.children)]
        while stack:
            for child in stack[-1]:
                if isinstance(child, AnimNode):
                    stack.append(iter(child.children))
                    break
                if isinstance(child, TrisRun):
                    yield child
            else:
                stack.pop()


# Pairs of attributes where the second state replaces the first (and the reverse).
# Each maps the directive to (state key, value). A None value removes the key.
_TOGGLES = {
    "ATTR_draw_enable": ("draw", None),
    "ATTR_draw_disable": ("draw", ("disable",)),
    "ATTR_cull": ("cull", None),
    "ATTR_no_cull": ("cull", ("no_cull",)),
    "ATTR_solid_camera": ("solid_camera", ("on",)),
    "ATTR_no_solid_camera": ("solid_camera", None),
    "ATTR_shadow": ("shadow", None),
    "ATTR_no_shadow": ("shadow", ("off",)),
    "ATTR_depth": ("depth", None),
    "ATTR_no_depth": ("depth", ("off",)),
    "ATTR_cockpit_hud": ("cockpit", ("hud",)),
    "ATTR_no_cockpit": ("cockpit", None),
    "ATTR_cockpit": ("cockpit", ("panel",)),
    "ATTR_hard_deck": ("hard", ("deck",)),
    "ATTR_no_hard": ("hard", None),
    "ATTR_light_level_reset": ("light_level", None),
    "ATTR_manip_none": ("manip", None),
}
# Directives whose arguments become the state value
_VALUED = {
    "ATTR_shiny_rat": "shiny",
    "ATTR_poly_os": "poly_os",
    "ATTR_blend": "blend",
    "ATTR_no_blend": "blend",
    "ATTR_shadow_blend": "blend",
    "ATTR_light_level": "light_level",
    "ATTR_cockpit_region": "cockpit",
    "ATTR_cockpit_device": "cockpit",
    "ATTR_cockpit_lit_only": "cockpit_lit_only",
    "ATTR_hard": "hard",
    "ATTR_layer_group": "layer_group",
    "ATTR_diffuse": "diffuse",
    "ATTR_diffuse_rgb": "diffuse_rgb",
    "ATTR_emission_rgb": "emission_rgb",
    "ATTR_specular_rgb": "specular_rgb",
    "ATTR_shade_flat": "shade",
    "ATTR_shade_smooth": "shade",
    "ATTR_landing_gear": "landing_gear",
    "ATTR_hud_glass": "hud_glass",
    "ATTR_wiper": "wiper",
    "ATTR_no_wiper": "wiper",
    "ATTR_rain_scale": "rain",
}
# These are only valid together with the manipulator that they follow
_MANIP_EXTRAS = (
    "ATTR_manip_wheel",
    "ATTR_manip_keyframe",
    "ATTR_manip_wrap",
    "ATTR_axis_detented",
)

_GLOBAL_DIRECTIVES = {
    "GLOBAL_no_blend",
    "GLOBAL_shadow_blend",
    "GLOBAL_specular",
    "GLOBAL_tint",
    "GLOBAL_luminance",
    "GLOBAL_cockpit_lit",
    "GLOBAL_no_shadow",
    "GLOBAL_diffuse_rgb",
    "GLOBAL_emission_rgb",
    "GLOBAL_shiny_rat",
    "BLEND_GLASS",
    "NORMAL_METALNESS",
    "NORMAL_DECAL_PARAMS",
    "SLOPE_LIMIT",
    "SLOPE_FLATTEN",
    "SLUNG_LOAD_WEIGHT",
    "PARTICLE_SYSTEM",
    "COCKPIT_REGION",
    "DEBUG",
    "EXPORT",
    "TILTED",
    "REQUIRE_EXTENSION",
    "RAIN_scale",
    "RAIN_SCALE",
    "RAIN_friction",
    "RAIN_look_out_dataref",
    "RAIN_bias",
    "WIPER_param",
    "WIPER_texture",
    "WIPER_texture_",
    "THERMAL_texture",
    "THERMAL_source",
    "THERMAL_source2",
    "TEXTURE_DRAPED_NORMAL",
    "TEXTURE_NORMAL_DRAPED",
    "DECAL",
    "DECAL_RGBA",
    "DECAL_PARAMS",
    "DECAL_PARAMS_PROJ",
    "NORMAL_DECAL_GRADIENT",
    "GRADIENT_PARAMS",
    "SPECULAR",
    "BUMP_LEVEL",
    "ATTR_bump_level",
    "GLOBAL_cockpit_lit_only",
}
_EXTRAS = {"MAGNET", "EMITTER", "SMOKE_BLACK", "SMOKE_WHITE"}
_LIGHT_NAMED = ("LIGHT_NAMED", "LIGHT_CUSTOM", "LIGHT_PARAM", "LIGHT_SPILL_CUSTOM")
_IGNORED = {"TRIS_break", "POINT_COUNTS", "OBJ"}


def _freeze(state: Dict[str, Any]) -> FrozenState:
    return tuple(sorted(state.items(), key=lambda kv: kv[0]))


def _floats(tokens: List[str]) -> Tuple[float, ...]:
    return tuple(float(t) for t in tokens)


def parse_obj_file(path: str) -> ObjFile:
    with open(path, "rb") as f:
        raw = f.read()
    return parse_obj(raw.decode("utf-8", errors="replace"), path)


def parse_obj(text: str, path: str = "") -> ObjFile:
    obj = ObjFile(path=path)
    lines = text.splitlines()

    # --- Header: line endings marker, version, "OBJ" ---------------------------------------
    index = 0
    header_seen = False
    while index < len(lines) and index < 6:
        token = lines[index].strip()
        index += 1
        if token == "OBJ":
            header_seen = True
            break
        if token.isdigit():
            obj.version = int(token)
    if not header_seen:
        raise ObjParseError(
            f"{os.path.basename(path) or 'text'} is not an OBJ8 file (no OBJ header)"
        )
    if obj.version < 800:
        raise ObjParseError(
            f"OBJ version {obj.version} is not supported, only OBJ8 (800 and later)"
        )

    state: Dict[str, Any] = {}
    manip_extras: List[Tuple[str, Tuple[str, ...]]] = []
    detents: List[Tuple[str, ...]] = []
    lod: Optional[Tuple[float, float]] = None

    stack: List[AnimNode] = [obj.root]
    # The block currently being filled by a *_begin ... *_end group
    op: Optional[AnimOp] = None
    last_comment = ""

    def frozen() -> FrozenState:
        current = dict(state)
        if "manip" in current:
            if manip_extras:
                current["manip_extras"] = tuple(manip_extras)
            if detents:
                current["manip_detents"] = tuple(detents)
        return _freeze(current)

    def unknown(name: str) -> None:
        obj.unknown[name] = obj.unknown.get(name, 0) + 1

    # The vertex and index tables are most of a big file, they are collected as text and converted in bulk
    vertex_lines: List[str] = []
    index_lines: List[str] = []

    for line_number, line in enumerate(lines[index:], start=index + 1):
        stripped = line.strip()
        if not stripped:
            continue
        lead = stripped[:3]
        if lead == "VT\t" or lead == "VT ":
            if "#" in stripped:
                stripped = stripped.partition("#")[0]
            vertex_lines.append(stripped[3:])
            continue
        if lead == "IDX":
            if "#" in stripped:
                stripped = stripped.partition("#")[0]
            index_lines.append(
                stripped[5:] if stripped.startswith("IDX10") else stripped[3:]
            )
            continue
        if stripped[0] == "#":
            comment = stripped.lstrip("# ").strip()
            if comment:
                last_comment = comment
            continue
        # Trailing comments
        hash_at = stripped.find("#")
        if hash_at > 0:
            stripped = stripped[:hash_at].rstrip()
        parts = stripped.split()
        name = parts[0]
        if name[:7].upper() == "GLOBAL_" and name[:7] != "GLOBAL_":
            name = "GLOBAL_" + name[7:]
        args = parts[1:]

        try:
            if name == "VLIGHT":
                obj.vlights.append(_floats(args[:6]))
            elif name == "TRIS":
                stack[-1].children.append(
                    TrisRun(int(args[0]), int(args[1]), frozen(), lod)
                )
            elif name == "ANIM_begin":
                node = AnimNode(comment=last_comment, lod=lod)
                stack[-1].children.append(node)
                stack.append(node)
                last_comment = ""
            elif name == "ANIM_end":
                if len(stack) > 1:
                    stack.pop()
                else:
                    obj.warnings.append(
                        f"line {line_number}: ANIM_end without ANIM_begin"
                    )
            elif name == "ANIM_trans":
                values = _floats(args[:6])
                dataref = ""
                keys: List[Tuple[float, Tuple[float, ...]]] = []
                if len(args) >= 9:
                    dataref = args[8]
                    keys = [
                        (float(args[6]), values[0:3]),
                        (float(args[7]), values[3:6]),
                    ]
                else:
                    keys = [(0.0, values[0:3])]
                stack[-1].ops.append(AnimOp("trans", dataref, keys=keys))
            elif name == "ANIM_rotate":
                axis = _floats(args[:3])
                a1, a2 = float(args[3]), float(args[4])
                dataref = ""
                keys = []
                if len(args) >= 8:
                    dataref = args[7]
                    keys = [(float(args[5]), (a1,)), (float(args[6]), (a2,))]
                else:
                    keys = [(0.0, (a1,))]
                stack[-1].ops.append(AnimOp("rotate", dataref, axis, keys))
            elif name == "ANIM_trans_begin":
                op = AnimOp("trans", args[0] if args else "")
                stack[-1].ops.append(op)
            elif name == "ANIM_rotate_begin":
                op = AnimOp(
                    "rotate", args[3] if len(args) > 3 else "", _floats(args[:3])
                )
                stack[-1].ops.append(op)
            elif name == "ANIM_trans_key":
                if op is not None:
                    op.keys.append((float(args[0]), _floats(args[1:4])))
            elif name == "ANIM_rotate_key":
                if op is not None:
                    op.keys.append((float(args[0]), (float(args[1]),)))
            elif name in ("ANIM_trans_end", "ANIM_rotate_end"):
                op = None
            elif name == "ANIM_keyframe_loop":
                # Applies to the op that was just ended
                ops = stack[-1].ops
                if ops:
                    ops[-1].loop = float(args[0])
            elif name in ("ANIM_show", "ANIM_hide"):
                stack[-1].visibility.append(
                    Visibility(
                        name[5:],
                        float(args[0]),
                        float(args[1]),
                        args[2] if len(args) > 2 else "",
                    )
                )
            elif name == "ATTR_LOD":
                lod = (float(args[0]), float(args[1]))
                if lod not in obj.lods:
                    obj.lods.append(lod)
                # State is fully independent for LODs
                state.clear()
                manip_extras.clear()
                detents.clear()
            elif name == "ATTR_reset":
                state.clear()
                manip_extras.clear()
                detents.clear()
            elif name in _TOGGLES:
                key, value = _TOGGLES[name]
                if (
                    key == "cockpit"
                    and value is not None
                    and name == "ATTR_cockpit_hud"
                ):
                    state[key] = value
                elif value is None:
                    state.pop(key, None)
                    if key == "manip":
                        manip_extras.clear()
                        detents.clear()
                else:
                    state[key] = value
            elif name == "ATTR_cockpit":
                state["cockpit"] = ("panel",)
            elif name in _VALUED:
                key = _VALUED[name]
                if name in ("ATTR_blend", "ATTR_no_blend", "ATTR_shadow_blend"):
                    state[key] = (name[5:], *args)
                elif name == "ATTR_cockpit_region":
                    state[key] = ("region", *args)
                elif name == "ATTR_cockpit_device":
                    state[key] = ("device", *args)
                elif name == "ATTR_poly_os" and args and float(args[0]) == 0:
                    state.pop(key, None)
                elif name == "ATTR_shiny_rat" and not args:
                    state.pop(key, None)
                else:
                    state[key] = tuple(args)
            elif name == "ATTR_axis_detent_range":
                detents.append(tuple(args))
            elif name in _MANIP_EXTRAS:
                manip_extras.append((name, tuple(args)))
            elif name.startswith("ATTR_manip_"):
                state["manip"] = (name[len("ATTR_manip_") :], *args)
                manip_extras.clear()
                detents.clear()
            elif name == "TEXTURE":
                obj.texture = " ".join(args)
            elif name == "TEXTURE_LIT":
                obj.texture_lit = " ".join(args)
            elif name == "TEXTURE_NORMAL":
                # TEXTURE_NORMAL [ratio] path
                obj.texture_normal = " ".join(
                    args[1:] if len(args) > 1 and _is_number(args[0]) else args
                )
                obj.globals.setdefault("TEXTURE_NORMAL_RATIO", []).append(
                    args[:1] if len(args) > 1 and _is_number(args[0]) else []
                )
            elif name == "TEXTURE_MAP":
                if len(args) >= 2:
                    obj.texture_maps[args[0]] = " ".join(args[1:])
            elif name == "TEXTURE_DRAPED":
                obj.texture_draped = " ".join(args)
            elif name == "TEXTURE_MODULATOR":
                obj.texture_modulator.append(" ".join(args))
            elif name == "POINT_COUNTS":
                if len(args) >= 4:
                    obj.point_counts = tuple(int(a) for a in args[:4])  # type: ignore
            elif name in _LIGHT_NAMED:
                position, rest, light_name = _light_position(name, args)
                obj.root and stack[-1].children.append(
                    Light(name[6:].lower(), position, light_name, rest, frozen(), lod)
                )
            elif name == "LIGHTS":
                first, count = int(args[0]), int(args[1])
                for i in range(first, first + count):
                    if i < len(obj.vlights):
                        v = obj.vlights[i]
                        stack[-1].children.append(
                            Light(
                                "vlight",
                                v[0:3],
                                "",
                                [str(c) for c in v[3:6]],
                                frozen(),
                                lod,
                            )
                        )
            elif name in _EXTRAS:
                stack[-1].children.append(Extra(name, args, frozen(), lod))
            elif name in _GLOBAL_DIRECTIVES or name.startswith(
                ("GLOBAL_", "WIPER_", "THERMAL_", "RAIN_")
            ):
                obj.globals.setdefault(name, []).append(args)
            elif name in _IGNORED:
                pass
            else:
                unknown(name)
        except (ValueError, IndexError) as e:
            obj.warnings.append(
                f"line {line_number}: could not read '{stripped[:60]}' ({e.__class__.__name__})"
            )

    if len(stack) > 1:
        obj.warnings.append(f"{len(stack) - 1} ANIM_begin blocks were never closed")

    obj.vertices = _to_vertex_array(vertex_lines, obj)
    obj.indices = _to_index_array(index_lines, obj)
    return obj


def _to_vertex_array(vertex_lines: List[str], obj: ObjFile) -> np.ndarray:
    if not vertex_lines:
        return np.zeros((0, 8))
    try:
        return np.array(" ".join(vertex_lines).split(), dtype=np.float64).reshape(-1, 8)
    except ValueError:
        # Something is wrong with at least one line, read them one by one and fix them up
        rows = []
        for number, text in enumerate(vertex_lines):
            try:
                values = [float(t) for t in text.split()[:8]]
            except ValueError:
                values = []
            if len(values) < 8:
                obj.warnings.append(
                    f"vertex {number} is incomplete, it was replaced with zeros"
                )
                values = (values + [0.0] * 8)[:8]
            rows.append(values)
        return np.array(rows, dtype=np.float64)


def _to_index_array(index_lines: List[str], obj: ObjFile) -> np.ndarray:
    if not index_lines:
        return np.zeros(0, dtype=np.int64)
    try:
        return np.array(" ".join(index_lines).split(), dtype=np.int64)
    except ValueError:
        values = []
        for text in index_lines:
            for token in text.split():
                try:
                    values.append(int(token))
                except ValueError:
                    obj.warnings.append(
                        f"index '{token}' is not a number, it was replaced with 0"
                    )
                    values.append(0)
        return np.array(values, dtype=np.int64)


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def _light_position(name: str, args: List[str]) -> Tuple[Vec3, List[str], str]:
    """Returns (position, remaining args, name) for a LIGHT_* line"""
    if name in ("LIGHT_NAMED", "LIGHT_PARAM"):
        return _floats(args[1:4]), args[4:], args[0]
    return _floats(args[0:3]), args[3:], ""
