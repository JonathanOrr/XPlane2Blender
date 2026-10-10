"""
The parts of an imported OBJ that become settings: click zones, light levels, lights, magnets and emitters.
"""

import math
from typing import TYPE_CHECKING, Dict

import bpy
import mathutils

from io_xplane2blender import (
    xplane_constants,
    xplane_display_sizes,
    xplane_light_sync,
    xplane_props,
)
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
    # Laminar name a dataref after no-op, which X-Plane ignores: kept as a label
    xplane_constants.MANIP_NOOP: ("noop_label",),
    xplane_constants.MANIP_DEVICE: ("cursor", "device", "tooltip"),
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

    EXTRA_EMPTY_SIZE = (
        0.05  # Meters, of the empties that are wheels, magnets or emitters
    )

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
    def _apply_object_state(
        self, blender_obj: bpy.types.Object, group: "_Group"
    ) -> None:
        state = group.object_state
        light_level = state.get("light_level")
        if light_level:
            x = blender_obj.xplane
            x.lightLevel = True
            try:
                x.lightLevel_v1 = _number(light_level[0])
                x.lightLevel_v2 = _number(light_level[1])
                x.lightLevel_dataref = light_level[2] if len(light_level) > 2 else ""
                # X-Plane 12 adds the brightness of the _LIT texture in nits
                if len(light_level) > 3:
                    x.lightLevel_photometric = True
                    x.lightLevel_brightness = max(0, round(_number(light_level[3])))
            except (ValueError, IndexError):
                self.report.warn(
                    f"{self.stem}: could not read ATTR_light_level {light_level}"
                )
        if "hud_glass" in state:
            blender_obj.xplane.hud_glass = True
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

    @staticmethod
    def _has_lift(manip, m) -> bool:
        """ATTR_manip_drag_rotate's lift (meters) is its 10th value after the cursor, with a second dataref"""
        try:
            lift = _number(manip[1 + 9])
        except (IndexError, ValueError):
            return False
        return (
            bool(m.dataref2.strip()) and abs(lift) > 1e-6 and bool(m.axis_detent_ranges)
        )

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
            if field_name == "device":
                if text in xplane_constants.DEVICES and text != xplane_constants.DEVICE_PLUGIN:
                    m.device_name = text
                else:
                    m.device_name, m.plugin_device = xplane_constants.DEVICE_PLUGIN, text
                continue
            if field_name in (
                "tooltip",
                "command",
                "positive_command",
                "negative_command",
                "dataref1",
                "dataref2",
                "noop_label",
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
                elif (
                    name == "ATTR_axis_detented"
                    and kind == xplane_constants.MANIP_DRAG_AXIS
                    and len(args) >= 6
                    # A second direction of length 0 drags nowhere (the C172 seaplane's water rudder has one)
                    and any(abs(_number(a)) > 1e-9 for a in args[:3])
                ):
                    # The second direction is the animation of the part itself, so it is the detent type,
                    # which the exporter writes from the animations
                    m.type = xplane_constants.MANIP_DRAG_AXIS_DETENT
                    m.dataref2 = "" if args[5] == "none" else args[5]
            for detent in detents:
                if len(detent) >= 3:
                    item = m.axis_detent_ranges.add()
                    item.start, item.end, item.height = (_number(v) for v in detent[:3])
        except ValueError:
            self.report.warn(
                f"{self.stem}: a wheel or detent setting could not be read as a number"
            )
        if kind == xplane_constants.MANIP_DRAG_ROTATE and self._has_lift(manip, m):
            # A drag rotate with a lift is the rotation with a lift (translation) child, which the exporter only
            # accepts as the drag rotate with detents type. Detent lines without a lift (a stop pit, as on the C172's
            # trim wheel) stay on the plain drag rotate
            m.type = xplane_constants.MANIP_DRAG_ROTATE_DETENT
            # The line's own range of the detent dataref (v2_min, v2_max were read with the others)
            m.detent_dataref_range = True
        self.has_manipulators = True
        self.report.manipulators_imported += 1

    # ---- lights ---------------------------------------------------------------------------
    @staticmethod
    def _exact_color(settings, rgb) -> None:
        """Custom lights may hold placeholder colors outside 0 to 1, such as -1, that the Blender color picker can not"""
        if any(not 0.0 <= c <= 1.0 for c in rgb):
            settings.enable_rgb_override = True
            settings.rgb_override_values = rgb

    def _lights_collection(self) -> bpy.types.Collection:
        """
        A file's lights in a collection of their own inside the file's, so that one click in the outliner selects or
        hides them all. Hidden, they are not exported, like anything hidden
        """
        if self._lights is None:
            # Not "Lights lights" for the A330's Lights.obj
            plain = not self.stem.lower().endswith(("light", "lights"))
            self._lights = bpy.data.collections.new(f"{self.stem} lights" if plain else f"{self.stem} (light objects)")
            self.collection.children.link(self._lights)
        return self._lights

    def _add_light(
        self, light: Light, parent, static: mathutils.Matrix, name: str
    ) -> None:
        # The importer sets both sides of every number the X-Plane light shares with its Blender light itself
        with xplane_light_sync.paused():
            self._build_light(light, parent, static, name)

    def _build_light(
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
            if self.options.light_strength > 0:
                # What the power is multiplied by, so that it can be taken out again (see xplane_light_sync)
                blender_light[xplane_light_sync.STRENGTH] = self.options.light_strength
        else:
            blender_light.energy = 0.0
        # Blender draws a spot's cone as far as its custom distance: short for a light that is off, not a line
        # across the cockpit, and as far as it reaches for one that lights
        xplane_display_sizes.fit_cone(
            blender_light, look.reach, blender_light.energy > 0, self.options.scale
        )
        obj = bpy.data.objects.new(self._clean(data_name), blender_light)
        self._lights_collection().objects.link(obj)
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
                # r g b a size dx dy dz width dataref
                x.type = xplane_constants.LIGHT_SPILL_CUSTOM
                nums = [_number(a) for a in light.args[:9]]
                self._exact_color(x, nums[0:3])
                x.spill_dim = max(0.0, min(1.0, nums[3]))
                x.size = nums[4]
                x.dataref = light.args[9] if len(light.args) > 9 else ""
        except (ValueError, IndexError):
            self.report.warn(
                f"{self.stem}: could not read a {light.kind} light, it was imported without its settings"
            )
        if look.illuminates and self.options.light_strength > 0:
            # A light that is on has the power its intensity asks for, however large (see xplane_light_sync)
            xplane_light_sync.push(blender_light)
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
                # The type and six numbers end the line; a debug name with spaces (Laminar's "magnet pilot") is the rest
                debug_name, magnet_type = " ".join(extra.args[:-7]), extra.args[-7]
                x, y, z, phi, theta, psi = map(float, extra.args[-6:])
                self._make_special_empty(
                    debug_name,
                    "magnet",
                    parent,
                    static,
                    (x, y, z),
                    (phi, theta, psi),
                    [magnet_type],
                )
            elif extra.kind == "ATTR_landing_gear":
                x, y, z, phi, theta, psi = map(float, extra.args[0:6])
                gear, wheel = (int(float(a)) for a in extra.args[6:8])
                self._make_special_empty(
                    f"wheel {gear}.{wheel}",
                    "wheel",
                    parent,
                    static,
                    (x, y, z),
                    (phi, theta, psi),
                    [gear, wheel],
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
        # Meant to be seen and picked, so not as small as the empties that only move parts
        empty.empty_display_size = self.EXTRA_EMPTY_SIZE * self.options.scale
        phi, theta, psi = angles
        # The reverse of what the exporter writes, after the turn of the frame it is in
        turn = mathutils.Euler(
            (math.radians(theta), math.radians(psi), math.radians(-phi)), "XYZ"
        )
        self._exact[empty] = self._exact[empty] @ turn.to_matrix().to_4x4()
        empty.matrix_basis = self._exact[empty]
        special = empty.xplane.special_empty_props
        if kind == "wheel":
            special.special_type = xplane_constants.EMPTY_USAGE_WHEEL
            special.wheel_props.gear_index, special.wheel_props.wheel_index = rest
        elif kind == "emitter":
            special.special_type = xplane_constants.EMPTY_USAGE_EMITTER_PARTICLE
            special.emitter_props.name = name
            if rest:
                special.emitter_props.index_enabled = True
                special.emitter_props.index = int(float(rest[0]))
        else:
            self.has_magnets = True
            special.special_type = xplane_constants.EMPTY_USAGE_MAGNET
            special.magnet_props.debug_name = name
            special.magnet_props.magnet_type_is_xpad = "xpad" in rest[0]
            special.magnet_props.magnet_type_is_flashlight = "flashlight" in rest[0]

    # ---- export setup --------------------------------------------------------------------
