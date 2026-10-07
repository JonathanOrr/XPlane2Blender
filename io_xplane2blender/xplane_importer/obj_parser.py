"""
A parser for X-Plane OBJ8 files (versions 800 to 1200) that has no dependency on Blender.

parse_obj() returns an ObjFile: the vertex and index tables, the global (header) directives,
and a tree of animation nodes holding every drawable thing (triangle runs, lights, emitters,
magnets...) together with the attribute state that was active when it was drawn.
Anything it does not understand is kept in ObjFile.unknown, never silently dropped.
"""

import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .obj_records import (
    _EXTRAS,
    _GLOBAL_DIRECTIVES,
    _IGNORED,
    _LIGHT_NAMED,
    _MANIP_EXTRAS,
    _TOGGLES,
    _VALUED,
    AnimNode,
    AnimOp,
    Extra,
    FrozenState,
    Light,
    ObjFile,
    ObjParseError,
    TrisRun,
    Vec3,
    Visibility,
)


def _freeze(state: Dict[str, Any]) -> FrozenState:
    return tuple(sorted(state.items(), key=lambda kv: kv[0]))


_NUMBER_PREFIX = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?")


# Numbers that had stray text after them and were read anyway, the parse loop turns them into warnings
_repaired: List[Tuple[str, float]] = []


def _float(text: str) -> float:
    """float(), but like X-Plane's C parsing it takes the number at the start of a token with stray text after it.
    Laminar's own Cessna 172 has 'ANIM_rotate_key -2.5.000000 -18', which X-Plane reads as -2.5
    """
    try:
        return float(text)
    except ValueError:
        found = _NUMBER_PREFIX.match(text)
        if not found:
            raise
        _repaired.append((text, float(found.group())))
        return _repaired[-1][1]


def _floats(tokens: List[str]) -> Tuple[float, ...]:
    return tuple(_float(t) for t in tokens)


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

    def note_repairs(line_number: int) -> None:
        if _repaired:
            shown = ", ".join(f"'{text}' as {value:g}" for text, value in _repaired)
            obj.warnings.append(
                f"line {line_number}: read {shown}, the way X-Plane does, but the file has a typo"
            )
            _repaired.clear()

    _repaired.clear()
    last_line = 0
    for line_number, line in enumerate(lines[index:], start=index + 1):
        note_repairs(last_line)
        last_line = line_number
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
                        (_float(args[6]), values[0:3]),
                        (_float(args[7]), values[3:6]),
                    ]
                else:
                    keys = [(0.0, values[0:3])]
                stack[-1].ops.append(AnimOp("trans", dataref, keys=keys))
            elif name == "ANIM_rotate":
                axis = _floats(args[:3])
                a1, a2 = _float(args[3]), _float(args[4])
                dataref = ""
                keys = []
                if len(args) >= 8:
                    dataref = args[7]
                    keys = [(_float(args[5]), (a1,)), (_float(args[6]), (a2,))]
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
                    op.keys.append((_float(args[0]), _floats(args[1:4])))
            elif name == "ANIM_rotate_key":
                if op is not None:
                    op.keys.append((_float(args[0]), (_float(args[1]),)))
            elif name in ("ANIM_trans_end", "ANIM_rotate_end"):
                op = None
            elif name == "ANIM_keyframe_loop":
                # Applies to the op that was just ended
                ops = stack[-1].ops
                if ops:
                    ops[-1].loop = _float(args[0])
            elif name in ("ANIM_show", "ANIM_hide"):
                stack[-1].visibility.append(
                    Visibility(
                        name[5:],
                        _float(args[0]),
                        _float(args[1]),
                        args[2] if len(args) > 2 else "",
                    )
                )
            elif name == "ATTR_LOD":
                lod = (_float(args[0]), _float(args[1]))
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
                elif name == "ATTR_poly_os" and args and _float(args[0]) == 0:
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

    note_repairs(last_line)
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
                values = [_float(t) for t in text.split()[:8]]
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
