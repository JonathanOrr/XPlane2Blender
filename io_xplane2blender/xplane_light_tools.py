"""
Helps author X-Plane lights without knowing lights.txt by heart:
- pick a light name from a searchable list that says what each light is (a spill that lights its surroundings,
  or a glow that lights nothing) and which parameters it takes,
- see which parameters a Library Light, Manual needs and whether the right number is filled in,
- preview in the viewport how X-Plane lights the scene: spill lights light their surroundings (custom spills out to
  their real reach), glow-only lights light nothing.

The preview only changes Blender settings the exporter never reads for that light type (power, except for Custom
lights where power is the exported alpha; cutoff distance; ray visibility and EEVEE factors), so it never changes
an export.
"""

import math
from typing import List, Optional, Tuple

import bpy
import mathutils

from . import xplane_display_sizes as display_sizes
from .xplane_constants import (
    LIGHT_AUTOMATIC,
    LIGHT_CUSTOM,
    LIGHT_NAMED,
    LIGHT_PARAM,
    LIGHT_SPILL_CUSTOM,
)
from .xplane_utils import xplane_light_params as light_params
from .xplane_utils import xplane_lights_txt_parser as parser

RAY_VISIBILITY = ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter")
EEVEE_FACTORS = ("diffuse_factor", "specular_factor", "volume_factor")


def parsed_light(name: str) -> Optional["parser.ParsedLight"]:
    parser.parse_lights_file()
    try:
        return parser.get_parsed_light(name.strip())
    except KeyError:
        return None


def formal_params(name: str) -> List[str]:
    """The names of the parameters a library light takes, in order, or an empty list for an unknown light or one with none"""
    parsed = parsed_light(name) if name.strip() else None
    return list(parsed.light_param_def) if parsed is not None else []


def seed_params(settings) -> bool:
    """
    Gives a library light with typed parameters a starting line when its line does not fit the light it names:
    parameters typed for another light mean something else here. Returns whether the line was replaced
    """
    formal = formal_params(settings.name)
    if (
        settings.type != LIGHT_PARAM
        or not formal
        or len(light_params.split_line(settings.params, len(formal))[0]) == len(formal)
    ):
        return False
    settings.params = light_params.default_line(formal)
    return True


def is_known(name: str) -> bool:
    return parsed_light(name) is not None


def kinds_of(name: str) -> Tuple[bool, bool]:
    """(spills, glows): whether the light lights its surroundings, and whether it has a visible halo"""
    parsed = parsed_light(name)
    if parsed is None:
        return False, False
    types = [o.overload_type for o in parsed.overloads]
    return any(t.startswith("SPILL") for t in types), any(t.startswith("BILLBOARD") for t in types)


def describe(name: str, with_params: bool = True) -> str:
    parsed = parsed_light(name)
    if parsed is None:
        return "Not in lights.txt: check the spelling"
    spills, glows = kinds_of(name)
    if spills and glows:
        what = "Glow and spill: a visible halo that also lights its surroundings"
    elif spills:
        what = "Spill: lights its surroundings, no visible halo"
    else:
        what = "Glow: a visible halo, lights nothing around it"
    if with_params and parsed.light_param_def:
        what += ". Takes " + " ".join(parsed.light_param_def)
    return what


def param_check(name: str, params: str) -> Tuple[List[str], str]:
    """The parameters a Library Light, Manual takes, and a problem with the typed values or an empty string"""
    parsed = parsed_light(name)
    if parsed is None:
        return [], ""
    wanted = list(parsed.light_param_def)
    if not wanted:
        return [], "This light takes no parameters: use the Named type"
    have = len(params.split())
    if have != len(wanted):
        return wanted, f"Needs {len(wanted)} value(s), has {have}"
    return wanted, ""


_name_items: List[Tuple[str, str, str]] = []


def _items(self, context):
    global _name_items
    if not _name_items:
        parser.parse_lights_file()
        for name in sorted(parser._parsed_lights_txt_content):
            spills, glows = kinds_of(name)
            tag = "glow + spill" if spills and glows else "spill" if spills else "glow"
            # The tag is in the visible name: search popups do not show descriptions
            _name_items.append((name, f"{name}   [{tag}]", describe(name)))
    return _name_items


class XPLANE_OT_light_pick_name(bpy.types.Operator):
    """Choose a light from lights.txt. The list says whether each light is a spill (lights its surroundings) or a glow (a halo that lights nothing)"""

    bl_idname = "xplane.light_pick_name"
    bl_label = "Choose X-Plane Light"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "light"

    light: bpy.props.EnumProperty(name="Light", items=_items)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "LIGHT"

    def execute(self, context):
        x = context.active_object.data.xplane
        x.name = self.light
        seed_params(x)
        self.report({"INFO"}, f"{self.light}: {describe(self.light)}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


# ---- Viewport preview -----------------------------------------------------------------------------------------


def _automatic_args(obj: bpy.types.Object, parsed) -> List[str]:
    """The values an Automatic light gets from its Blender light, close enough for a preview"""
    data = obj.data
    x = data.xplane
    direction = obj.matrix_world.to_3x3() @ mathutils.Vector((0.0, 0.0, -1.0))
    # X-Plane is y up, Blender is z up
    dx, dy, dz = direction.x, direction.z, -direction.y
    width = math.cos(data.spot_size / 2) if data.type == "SPOT" else 1.0
    size = x.param_intensity_new if parsed.name in parser.SIZE_AS_INTENSITY else x.param_size
    values = {
        "R": data.color[0],
        "G": data.color[1],
        "B": data.color[2],
        "SIZE": size,
        "INTENSITY": x.param_intensity_new,
        "DX": dx,
        "DY": dy,
        "DZ": dz,
        "WIDTH": width,
        "INDEX": x.param_index,
        "FREQ": x.param_freq,
        "PHASE": x.param_phase,
    }
    return [str(values.get(p, 0)) for p in parsed.light_param_def]


def preview_look(obj: bpy.types.Object) -> Optional[Tuple[bool, float, Optional[float]]]:
    """(lights the scene, watts with the light on, reach in meters or None), or None when there is nothing to preview"""
    from .xplane_importer import lights as importer_lights
    from .xplane_importer.obj_parser import Light

    x = obj.data.xplane
    if x.type == LIGHT_SPILL_CUSTOM:
        return True, importer_lights.watts_for_size(x.size), x.size
    if x.type == LIGHT_CUSTOM:
        return False, 0.0, None
    if x.type in (LIGHT_NAMED, LIGHT_PARAM, LIGHT_AUTOMATIC):
        parsed = parsed_light(x.name) if x.name.strip() else None
        if parsed is None:
            return None
        if x.type == LIGHT_NAMED:
            light = Light("named", (0.0, 0.0, 0.0), parsed.name, [])
        elif x.type == LIGHT_PARAM:
            light = Light("param", (0.0, 0.0, 0.0), parsed.name, x.params.split())
        else:
            light = Light("param", (0.0, 0.0, 0.0), parsed.name, _automatic_args(obj, parsed))
        look = importer_lights.look_of(light)
        return look.illuminates, look.watts, None
    return None


def apply_preview(obj: bpy.types.Object, strength: float) -> bool:
    look = preview_look(obj)
    if look is None:
        return False
    illuminates, watts, reach = look
    data = obj.data
    for ray in RAY_VISIBILITY:
        if hasattr(obj, ray):
            setattr(obj, ray, illuminates)
    for factor in EEVEE_FACTORS:
        if hasattr(data, factor):
            setattr(data, factor, 1.0 if illuminates else 0.0)
    # The power of a Custom light is its exported alpha, it must stay as the author set it
    if data.xplane.type != LIGHT_CUSTOM:
        data.energy = watts * strength if illuminates else 0.0
    # How far the cone is drawn follows how far the light lights
    display_sizes.fit_cone(data, reach, display_sizes.is_lit(data))
    return True


class XPLANE_OT_lights_preview(bpy.types.Operator):
    """Make lights look in the viewport the way X-Plane draws them: spills light their surroundings (custom spills out to their real reach), glows light nothing. Only settings the exporter never reads are changed"""

    bl_idname = "xplane.lights_preview"
    bl_label = "Preview Lights As In X-Plane"
    bl_options = {"REGISTER", "UNDO"}

    strength: bpy.props.FloatProperty(
        name="Strength",
        description="Multiplies the power of the lights that light the scene. X-Plane exposes differently from Blender",
        default=1.0,
        min=0.0,
        soft_max=20.0,
    )
    selected_only: bpy.props.BoolProperty(
        name="Selected Only", description="Only the selected lights, otherwise every light in the scene", default=True
    )

    def execute(self, context):
        objects = context.selected_objects if self.selected_only else context.scene.objects
        lights = [o for o in objects if o.type == "LIGHT"]
        changed = sum(1 for o in lights if apply_preview(o, self.strength))
        skipped = len(lights) - changed
        text = f"Previewed {changed} light(s)"
        if skipped:
            text += f"; {skipped} without a known X-Plane light were left alone"
        self.report({"INFO"}, text)
        return {"FINISHED"}


_classes = (XPLANE_OT_light_pick_name, XPLANE_OT_lights_preview)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
