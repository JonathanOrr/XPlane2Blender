"""
The parts of an imported OBJ that become settings: click zones, light levels, lights, magnets and emitters.
"""

import math
from typing import TYPE_CHECKING, Dict

import bpy
import mathutils

from io_xplane2blender import xplane_constants, xplane_props
from io_xplane2blender.xplane_constants import MANIP_DRAG_ROTATE
from io_xplane2blender.xplane_types.xplane_manipulator import SETTINGS_WRITTEN

from . import lights
from . import transforms as T
from .obj_parser import Extra, Light

if TYPE_CHECKING:
    from .obj_builder import _Group

# Arguments of each ATTR_manip_* in file order, as the exporter writes them. "cursor" is first for all of them.
# Drag rotate's center, axis, angles and lift come from its animation, which is imported as animation
_MANIP_ARGS = {
    **SETTINGS_WRITTEN,
    MANIP_DRAG_ROTATE: (
        "cursor",
        *[None] * 9,
        "v1_min",
        "v1_max",
        "v2_min",
        "v2_max",
        "dataref1",
        "dataref2",
        "tooltip",
    ),
}


def _number(text: str) -> float:
    """float() that also reads a decimal comma, which some hand edited OBJ files have"""
    return float(text.replace(",", "."))


class PartsBuilder:
    """The settings half of ObjBuilder"""

    def _object_name(self, group: "_Group") -> str:
        manip = group.object_state.get("manip")
        if manip:
            args = _MANIP_ARGS.get(manip[0])
            if args and "tooltip" in args:
                tooltip = self._manip_values(manip).get("tooltip", "")
                if tooltip:
                    return self._clean(tooltip)
            command = self._manip_values(manip).get("command")
            if command:
                return self._clean(command.split("/")[-1])
        return self._clean(group.name_hint)

    @staticmethod
    def _clean(name: str) -> str:
        return (name or "object").strip()[:60] or "object"

    # ---- object level settings -----------------------------------------------------------
    def _apply_object_state(self, blender_obj: bpy.types.Object, group: "_Group") -> None:
        state = group.object_state
        light_level = state.get("light_level")
        if light_level:
            x = blender_obj.xplane
            x.lightLevel = True
            try:
                x.lightLevel_v1 = _number(light_level[0])
                x.lightLevel_v2 = _number(light_level[1])
                x.lightLevel_dataref = light_level[2] if len(light_level) > 2 else ""
            except (ValueError, IndexError):
                self.report.warn(
                    f"{self.stem}: could not read ATTR_light_level {light_level}"
                )
        manip = state.get("manip")
        if manip and self.options.import_manipulators:
            self._apply_manipulator(
                blender_obj,
                manip,
                state.get("manip_extras", ()),
                state.get("manip_detents", ()),
            )

    @staticmethod
    def _manip_values(manip: tuple) -> Dict[str, str]:
        kind, *args = manip
        names = _MANIP_ARGS.get(kind)
        if names is None:
            return {}
        values: Dict[str, str] = {}
        for position, field_name in enumerate(names):
            if position >= len(args):
                break
            if field_name == "tooltip":
                values["tooltip"] = " ".join(args[position:])
                break
            if field_name:
                values[field_name] = args[position]
        return values

    def _apply_manipulator(self, blender_obj, manip, extras, detents) -> None:
        kind = manip[0]
        m = blender_obj.xplane.manip
        valid_types = {item[0] for item in xplane_props.MANIP_TYPE_ITEMS}
        if kind == "none" or kind not in _MANIP_ARGS or kind not in valid_types:
            self.report.warn(f"{self.stem}: manipulator type '{kind}' is not supported")
            return
        m.enabled = True
        m.type = kind
        m.autodetect_datarefs = False
        m.autodetect_settings_opt_in = False
        cursors = {i.identifier for i in m.bl_rna.properties["cursor"].enum_items}
        for field_name, text in self._manip_values(manip).items():
            if field_name == "cursor":
                if text in cursors:
                    m.cursor = text
                continue
            if field_name in (
                "tooltip",
                "command",
                "positive_command",
                "negative_command",
                "dataref1",
                "dataref2",
            ):
                setattr(
                    m,
                    field_name,
                    "" if text == "none" and field_name.startswith("dataref") else text,
                )
                continue
            try:
                setattr(m, field_name, _number(text))
            except ValueError:
                self.report.warn(
                    f"{self.stem}: manipulator value '{text}' is not a number, it was left at its default"
                )
        try:
            for name, args in extras:
                if name == "ATTR_manip_wheel" and args:
                    m.wheel_delta = _number(args[0])
            for detent in detents:
                if len(detent) >= 3:
                    item = m.axis_detent_ranges.add()
                    item.start, item.end, item.height = (_number(v) for v in detent[:3])
        except ValueError:
            self.report.warn(
                f"{self.stem}: a wheel or detent setting could not be read as a number"
            )
        self.has_manipulators = True
        self.report.manipulators_imported += 1

    # ---- lights ---------------------------------------------------------------------------
    @staticmethod
    def _exact_color(settings, rgb) -> None:
        """Custom lights may hold placeholder colors outside 0 to 1, such as -1, that the Blender color picker can not"""
        if any(not 0.0 <= c <= 1.0 for c in rgb):
            settings.enable_rgb_override = True
            settings.rgb_override_values = rgb

    def _add_light(
        self, light: Light, parent, static: mathutils.Matrix, name: str
    ) -> None:
        look = lights.look_of(light)
        matrix = static @ T.translation_xp(light.position)
        data_name = light.name or light.kind
        blender_light = bpy.data.lights.new(self._clean(data_name), look.kind)
        blender_light.color = look.color
        blender_light.shadow_soft_size = 0.01
        if look.kind == "SPOT":
            blender_light.spot_size = look.spot_size
            blender_light.spot_blend = 0.2
        if look.illuminates:
            # Spill lights are dataref driven and off in the parked pose, "Light Strength" switches them on
            blender_light["xplane_watts_when_on"] = look.watts
            blender_light.energy = look.watts * self.options.light_strength
        else:
            blender_light.energy = 0.0
        obj = bpy.data.objects.new(self._clean(data_name), blender_light)
        self.collection.objects.link(obj)
        obj.parent = parent
        base = T.matrix_to_blender(matrix)
        if look.direction is not None:
            # A spot points along its -Z, the exporter reads the light direction from there
            pointing = T.vec_to_blender(look.direction)
            turn = mathutils.Vector((0.0, 0.0, -1.0)).rotation_difference(pointing)
            base = base @ turn.to_matrix().to_4x4()
        obj.matrix_basis = base
        if not look.illuminates:
            # Billboards and custom lights are only halos in X-Plane, they must not light the scene in Cycles or EEVEE
            for ray in (
                "visible_diffuse",
                "visible_glossy",
                "visible_transmission",
                "visible_volume_scatter",
            ):
                if hasattr(obj, ray):
                    setattr(obj, ray, False)
        if parent is not None and parent.name in self._hidden:
            self._hide(obj)
        self._flag_lod(obj, light.lod)
        x = blender_light.xplane
        try:
            if light.kind == "named":
                x.type = xplane_constants.LIGHT_NAMED
                x.name = light.name
            elif light.kind == "param":
                x.type = xplane_constants.LIGHT_PARAM
                x.name = light.name
                x.params = " ".join(light.args)
            elif light.kind == "custom":
                # r g b a size s1 t1 s2 t2 dataref, the exporter writes the Blender power as the alpha
                x.type = xplane_constants.LIGHT_CUSTOM
                nums = [_number(a) for a in light.args[:9]]
                blender_light.energy = nums[3]
                self._exact_color(x, nums[0:3])
                x.size = nums[4]
                x.uv = nums[5:9]
                x.dataref = light.args[9] if len(light.args) > 9 else ""
            elif light.kind == "vlight":
                # X-Plane 9 lights have no X-Plane 12 equivalent. With no light chosen it is listed as
                # unfinished work, keeping its color; 9.7 to 9.9 meant traffic, strobe and pulsing
                x.type = xplane_constants.LIGHT_AUTOMATIC
                x.name = ""
                rgb = [_number(a) for a in light.args[:3]]
                if all(c < 9.0 for c in rgb):
                    blender_light.color = [min(max(abs(c), 0.0), 1.0) for c in rgb]
            elif light.kind == "spill_custom":
                # r g b a size dx dy dz width dataref, the exporter always writes an alpha of 1
                x.type = xplane_constants.LIGHT_SPILL_CUSTOM
                nums = [_number(a) for a in light.args[:9]]
                self._exact_color(x, nums[0:3])
                x.size = nums[4]
                x.dataref = light.args[9] if len(light.args) > 9 else ""
                if abs(nums[3] - 1.0) > 1e-6:
                    self.report.warn(
                        f"{self.stem}: a spill light has an alpha of {nums[3]:g}, the exporter always writes 1"
                    )
        except (ValueError, IndexError):
            self.report.warn(
                f"{self.stem}: could not read a {light.kind} light, it was imported without its settings"
            )
        self.objects.append(obj)
        self.report.lights_imported += 1

    # ---- magnets, emitters ------------------------------------------------------------------
    def _add_extra(self, extra: Extra, parent, static: mathutils.Matrix) -> None:
        try:
            if extra.kind == "EMITTER":
                name, x, y, z, phi, theta, psi = extra.args[0], *map(
                    float, extra.args[1:7]
                )
                self._make_special_empty(
                    name,
                    "emitter",
                    parent,
                    static,
                    (x, y, z),
                    (phi, theta, psi),
                    extra.args[7:],
                )
            elif extra.kind == "MAGNET":
                debug_name, magnet_type = extra.args[0], extra.args[1]
                x, y, z, phi, theta, psi = map(float, extra.args[2:8])
                self._make_special_empty(
                    debug_name,
                    "magnet",
                    parent,
                    static,
                    (x, y, z),
                    (phi, theta, psi),
                    [magnet_type],
                )
            else:
                self.report.warn(
                    f"{self.stem}: {extra.kind} is not supported and was skipped"
                )
        except (ValueError, IndexError):
            self.report.warn(f"{self.stem}: could not read a {extra.kind} line")

    def _make_special_empty(
        self, name, kind, parent, static, position, angles, rest
    ) -> None:
        matrix = static @ T.translation_xp(position)
        empty = self._make_empty(name, parent, matrix)
        phi, theta, psi = angles
        # The reverse of what the exporter writes
        empty.rotation_euler = (
            math.radians(theta),
            math.radians(psi),
            math.radians(-phi),
        )
        special = empty.xplane.special_empty_props
        if kind == "emitter":
            special.special_type = xplane_constants.EMPTY_USAGE_EMITTER_PARTICLE
            special.emitter_props.name = name
            if rest:
                special.emitter_props.index_enabled = True
                special.emitter_props.index = int(float(rest[0]))
        else:
            special.special_type = xplane_constants.EMPTY_USAGE_MAGNET
            special.magnet_props.debug_name = name
            special.magnet_props.magnet_type_is_xpad = "xpad" in rest[0]
            special.magnet_props.magnet_type_is_flashlight = "flashlight" in rest[0]

    # ---- export setup --------------------------------------------------------------------
