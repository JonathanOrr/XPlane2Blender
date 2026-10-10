"""
What an OBJ parses into (ObjFile and the records in its animation tree), and the tables of directives the
parser knows.
"""

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
    # Opened by an animation or show / hide line that follows geometry in its block (Laminar's older files): X-Plane
    # applies it to what follows only. It ends with the block's ANIM_end
    implicit: bool = False


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
    "ATTR_shade_flat": ("shade", ("flat",)),
    "ATTR_shade_smooth": ("shade", None),
    "ATTR_no_depth": ("depth", ("off",)),
    "ATTR_cockpit_hud": ("cockpit", ("hud",)),
    "ATTR_no_cockpit": ("cockpit", None),
    "ATTR_cockpit": ("cockpit", ("panel",)),
    "ATTR_hard_deck": ("hard", ("deck",)),
    "ATTR_no_hard": ("hard", None),
    "ATTR_light_level_reset": ("light_level", None),
    "ATTR_albedo_opacity_reset": ("albedo_opacity", None),
    "ATTR_hud_reset": ("hud_glass", None),
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
    # Not in the OBJ8 spec but read by X-Plane 12 (12.05 fixed a bug in it): fades the albedo by a dataref
    "ATTR_albedo_opacity": "albedo_opacity",
    "ATTR_cockpit_region": "cockpit",
    "ATTR_cockpit_device": "cockpit",
    "ATTR_cockpit_lit_only": "cockpit_lit_only",
    "ATTR_hard": "hard",
    "ATTR_layer_group": "layer_group",
    "ATTR_diffuse": "diffuse",
    "ATTR_diffuse_rgb": "diffuse_rgb",
    "ATTR_emission_rgb": "emission_rgb",
    "ATTR_specular_rgb": "specular_rgb",
    "ATTR_hud_glass": "hud_glass",
    "ATTR_wiper": "wiper",
    "ATTR_no_wiper": "wiper",
    "ATTR_rain_scale": "rain",
}
# These are only valid together with the manipulator that they follow
_MANIP_EXTRAS = (
    "ATTR_manip_wheel",
    "ATTR_manip_keyframe",
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
    "NORMAL_DECAL_PARAMS_PROJ",
    "DECAL_LIB",
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
# ATTR_landing_gear marks where a wheel is in its animation, like an emitter, it is not a state of the triangles
_EXTRAS = {"MAGNET", "EMITTER", "SMOKE_BLACK", "SMOKE_WHITE", "ATTR_landing_gear"}
_LIGHT_NAMED = ("LIGHT_NAMED", "LIGHT_CUSTOM", "LIGHT_PARAM", "LIGHT_SPILL_CUSTOM")
_IGNORED = {"TRIS_break", "POINT_COUNTS", "OBJ"}
