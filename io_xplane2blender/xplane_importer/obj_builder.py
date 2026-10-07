"""Builds the Blender data for one parsed OBJ"""

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import bpy
import mathutils
import numpy as np

from io_xplane2blender import xplane_constants, xplane_helpers, xplane_xp12

from . import lights
from . import transforms as T
from .common import ImportOptions, ImportReport
from .defaults import nearest_key_index, show_hide_visible
from .materials import MaterialFactory, TextureResolver
from .mesh_builder import build_mesh
from .obj_parser import AnimNode, AnimOp, Extra, Light, ObjFile, TrisRun, Visibility

# State keys that belong to the Blender object, the rest belong to the material
_OBJECT_STATE_KEYS = {"manip", "manip_extras", "manip_detents", "light_level"}

# Arguments of each ATTR_manip_* in file order. "cursor" is first for all of them
_MANIP_ARGS: Dict[str, Tuple[str, ...]] = {
    "drag_xy": (
        "cursor",
        "dx",
        "dy",
        "v1_min",
        "v1_max",
        "v2_min",
        "v2_max",
        "dataref1",
        "dataref2",
        "tooltip",
    ),
    "drag_axis": ("cursor", "dx", "dy", "dz", "v1", "v2", "dataref1", "tooltip"),
    "drag_axis_pix": ("cursor", "dx", "step", "exp", "v1", "v2", "dataref1", "tooltip"),
    "drag_rotate": (
        "cursor",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        "v1_min",
        "v1_max",
        "v2_min",
        "v2_max",
        "dataref1",
        "dataref2",
        "tooltip",
    ),
    "command": ("cursor", "command", "tooltip"),
    "command_axis": (
        "cursor",
        "dx",
        "dy",
        "dz",
        "positive_command",
        "negative_command",
        "tooltip",
    ),
    "command_knob": ("cursor", "positive_command", "negative_command", "tooltip"),
    "command_switch_up_down": (
        "cursor",
        "positive_command",
        "negative_command",
        "tooltip",
    ),
    "command_switch_left_right": (
        "cursor",
        "positive_command",
        "negative_command",
        "tooltip",
    ),
    "command_knob2": ("cursor", "command", "tooltip"),
    "command_switch_up_down2": ("cursor", "command", "tooltip"),
    "command_switch_left_right2": ("cursor", "command", "tooltip"),
    "push": ("cursor", "v_down", "v_up", "dataref1", "tooltip"),
    "radio": ("cursor", "v_down", "dataref1", "tooltip"),
    "toggle": ("cursor", "v_on", "v_off", "dataref1", "tooltip"),
    "delta": ("cursor", "v_down", "v_hold", "v1_min", "v1_max", "dataref1", "tooltip"),
    "wrap": ("cursor", "v_down", "v_hold", "v1_min", "v1_max", "dataref1", "tooltip"),
    "axis_knob": (
        "cursor",
        "v1",
        "v2",
        "click_step",
        "hold_step",
        "dataref1",
        "tooltip",
    ),
    "axis_switch_up_down": (
        "cursor",
        "v1",
        "v2",
        "click_step",
        "hold_step",
        "dataref1",
        "tooltip",
    ),
    "axis_switch_left_right": (
        "cursor",
        "v1",
        "v2",
        "click_step",
        "hold_step",
        "dataref1",
        "tooltip",
    ),
    "noop": (),
}


def _number(text: str) -> float:
    """float() that also reads a decimal comma, which some hand edited OBJ files have"""
    return float(text.replace(",", "."))


@dataclass
class _Group:
    parent: Optional[bpy.types.Object]
    matrix_xp: mathutils.Matrix
    lod: Optional[tuple]
    object_state: dict
    name_hint: str
    runs: List[Tuple[TrisRun, int]] = field(
        default_factory=list
    )  # (run, material slot)
    materials: List[bpy.types.Material] = field(default_factory=list)
    material_index: Dict[tuple, int] = field(default_factory=dict)


@dataclass
class BuiltObj:
    collection: bpy.types.Collection
    objects: List[bpy.types.Object]
    has_manipulators: bool
    obj: ObjFile


class ObjBuilder:
    def __init__(
        self,
        obj: ObjFile,
        options: ImportOptions,
        report: ImportReport,
        parent_collection: Optional[bpy.types.Collection] = None,
        name: str = "",
        livery_objects_dir: str = "",
        objects_root: str = "",
        base_matrix: Optional[mathutils.Matrix] = None,
    ) -> None:
        self.obj = obj
        self.options = options
        self.report = report
        self.parent_collection = parent_collection
        self.stem = (
            name
            or options.collection_name
            or os.path.splitext(os.path.basename(obj.path))[0]
            or "object"
        )
        self.collection: bpy.types.Collection = None
        self.resolver = TextureResolver(
            os.path.dirname(obj.path), livery_objects_dir, objects_root
        )
        # X-Plane space placement of the whole object, used by aircraft where the .acf moves objects
        self.base_matrix = (
            base_matrix if base_matrix is not None else mathutils.Matrix.Identity(4)
        )
        self.materials = MaterialFactory(obj, self.resolver, options, report)
        self.vertices = obj.vertices
        self.indices = obj.indices
        self.objects: List[bpy.types.Object] = []
        self.has_manipulators = False
        self._groups: Dict[tuple, _Group] = {}
        self._first_lod = obj.lods[0] if obj.lods else None
        self._hidden = set()  # names of objects X-Plane would not draw by default
        self._light_count = 0

    # ------------------------------------------------------------------------------------
    def build(self) -> BuiltObj:
        self.collection = bpy.data.collections.new(self.stem)
        (self.parent_collection or bpy.context.scene.collection).children.link(
            self.collection
        )

        self._walk(self.obj.root, None, self.base_matrix, self.stem)
        self._flush_groups()
        self._setup_layer()
        self.report.files_imported += 1
        for message in self.obj.warnings[:20]:
            self.report.warn(f"{self.stem}: {message}")
        for directive, count in sorted(self.obj.unknown.items()):
            self.report.warn(
                f"{self.stem}: unsupported directive {directive} ({count}x) was skipped"
            )
        return BuiltObj(self.collection, self.objects, self.has_manipulators, self.obj)

    # ---- tree walk -------------------------------------------------------------------
    def _lod_index(self, lod: Optional[tuple]) -> int:
        """Which of the four LOD buckets of the add-on an ATTR_LOD range is, or -1 for all of them"""
        if lod is None or not self.options.all_lods or lod not in self.obj.lods:
            return -1
        index = self.obj.lods.index(lod)
        return index if index < 4 else -1

    def _flag_lod(self, blender_obj: bpy.types.Object, lod: Optional[tuple]) -> None:
        index = self._lod_index(lod)
        if index >= 0:
            # Without "override" the add-on takes the buckets of the parent, which has none
            blender_obj.xplane.override_lods = True
            blender_obj.xplane.lod[index] = True

    def _wanted_lod(self, lod: Optional[tuple]) -> bool:
        if lod is None or self.options.all_lods:
            return True
        return lod == self._first_lod

    def _walk(
        self,
        node: AnimNode,
        parent: Optional[bpy.types.Object],
        static: mathutils.Matrix,
        name: str,
    ) -> None:
        if node is not self.obj.root or node.visibility:
            # Show and hide lines before the first ANIM_begin cover the whole file
            parent, static = self._apply_node_transforms(node, parent, static, name)
        node_name = node.comment or name
        for child in node.children:
            if isinstance(child, AnimNode):
                if self._wanted_lod(child.lod):
                    self._walk(child, parent, static, node_name)
            elif isinstance(child, TrisRun):
                if self._wanted_lod(child.lod) and child.count >= 3:
                    self._add_run(child, parent, static, node_name)
            elif isinstance(child, Light):
                if self.options.import_lights and self._wanted_lod(child.lod):
                    self._add_light(child, parent, static, node_name)
            elif isinstance(child, Extra):
                if self._wanted_lod(child.lod):
                    self._add_extra(child, parent, static)

    # ---- animation nodes -----------------------------------------------------------------
    def _apply_node_transforms(self, node, parent, static, name):
        """Creates the Empties an ANIM block needs. Returns the parent and the static matrix for its contents"""
        # X-Plane space matrix of everything that is static since the last Empty
        pending = static.copy()
        shows = node.visibility if self.options.import_animations else []
        label = node.comment or name

        if shows:
            # Visibility covers everything in the block, so it goes on the outermost Empty
            holder = self._make_empty(label + " visibility", parent, pending)
            for vis in shows:
                self._add_dataref(
                    holder,
                    vis.dataref,
                    "show" if vis.kind == "show" else "hide",
                    v1=vis.v1,
                    v2=vis.v2,
                    loop=vis.loop,
                )
                if self.options.hide_default_hidden and not show_hide_visible(
                    vis.kind, vis.v1, vis.v2, vis.dataref
                ):
                    self._hide(holder)
            self.report.animations_imported += 1
            parent, pending = holder, mathutils.Matrix.Identity(4)

        for op in node.ops:
            if op.is_static or not self.options.import_animations:
                pending = pending @ self._static_matrix(op)
                continue
            parent = self._make_dynamic_empty(op, parent, pending, label)
            pending = mathutils.Matrix.Identity(4)
        return parent, pending

    @staticmethod
    def _static_matrix(op: AnimOp) -> mathutils.Matrix:
        value = op.static_value
        if op.kind == "trans":
            return T.translation_xp(value)
        return T.rotation_xp(op.axis, value[0])

    def _make_empty(
        self, name: str, parent, matrix_xp: mathutils.Matrix
    ) -> bpy.types.Object:
        empty = bpy.data.objects.new(self._clean(name), None)
        empty.empty_display_type = "PLAIN_AXES"
        empty.empty_display_size = 0.02 * max(self.options.scale, 1e-6) * 10
        self.collection.objects.link(empty)
        empty.parent = parent
        empty.matrix_basis = T.matrix_to_blender(matrix_xp)
        if parent is not None and parent.name in self._hidden:
            self._hide(empty)
        self.objects.append(empty)
        self.report.objects_imported += 1
        return empty

    def _make_dynamic_empty(
        self, op: AnimOp, parent, pending: mathutils.Matrix, label: str
    ) -> bpy.types.Object:
        name = f"{label} {op.dataref.split('/')[-1]}"
        pending_bl = T.matrix_to_blender(pending)
        keys = sorted(op.keys, key=lambda k: k[0])
        # The key nearest the dataref's default value goes on frame 1, so the scene opens in the parked pose
        first_frame = 1 - nearest_key_index([k[0] for k in keys], op.dataref)
        if op.kind == "trans":
            # Rotation in the static part goes on a parent, translation is folded into the keys
            if T.has_rotation(pending_bl):
                parent = self._make_empty(name + " base", parent, pending)
                offset = mathutils.Vector((0, 0, 0))
            else:
                offset = pending_bl.to_translation()
            empty = self._make_empty(name, parent, mathutils.Matrix.Identity(4))
            for i, (value, vec) in enumerate(keys):
                empty.location = offset + T.vec_to_blender(vec) * self.options.scale
                self._key(empty, "location", first_frame + i, op, value)
        else:
            if T.has_rotation(pending_bl):
                parent = self._make_empty(name + " base", parent, pending)
                location_xp = mathutils.Matrix.Identity(4)
            else:
                location_xp = pending
            empty = self._make_empty(name, parent, location_xp)
            index, sign = T.principal_axis(op.axis)
            axis_bl = (
                T.vec_to_blender(op.axis).normalized()
                if mathutils.Vector(op.axis).length
                else mathutils.Vector((0, 0, 1))
            )
            if index < 0:
                empty.rotation_mode = "AXIS_ANGLE"
            for i, (value, (angle,)) in enumerate(keys):
                if index >= 0:
                    empty.rotation_euler = (0, 0, 0)
                    empty.rotation_euler[index] = sign * math.radians(angle)
                    self._key(
                        empty,
                        "rotation_euler",
                        first_frame + i,
                        op,
                        value,
                        array_index=index,
                    )
                else:
                    empty.rotation_axis_angle = (math.radians(angle), *axis_bl)
                    self._key(empty, "rotation_axis_angle", first_frame + i, op, value)
        self._finish_animation(empty)
        self.report.animations_imported += 1
        return empty

    def _key(
        self,
        empty,
        data_path: str,
        frame: int,
        op: AnimOp,
        value: float,
        array_index: int = -1,
    ) -> None:
        if not empty.xplane.datarefs:
            self._add_dataref(empty, op.dataref, "transform", loop=op.loop)
        dataref = empty.xplane.datarefs[0]
        dataref.value = value
        dataref.keyframe_insert(data_path="value", frame=frame)
        if array_index >= 0:
            empty.keyframe_insert(data_path=data_path, index=array_index, frame=frame)
        else:
            empty.keyframe_insert(data_path=data_path, frame=frame)

    @staticmethod
    def _finish_animation(empty: bpy.types.Object) -> None:
        """X-Plane interpolates linearly between keys"""
        try:
            fcurves = xplane_helpers.get_action_fcurves(empty)
        except Exception:
            fcurves = []
        for fcurve in fcurves:
            for point in fcurve.keyframe_points:
                point.interpolation = "LINEAR"
            fcurve.update()

    def _hide(self, obj: bpy.types.Object) -> None:
        """Hides what X-Plane does not draw with the datarefs at their default values"""
        self._hidden.add(obj.name)
        obj.hide_viewport = True
        obj.hide_render = True

    def _add_dataref(
        self,
        obj,
        path: str,
        anim_type: str,
        v1: float = 0.0,
        v2: float = 0.0,
        loop: float = 0.0,
    ) -> None:
        dataref = obj.xplane.datarefs.add()
        dataref.path = path
        dataref.anim_type = {
            "transform": xplane_constants.ANIM_TYPE_TRANSFORM,
            "show": xplane_constants.ANIM_TYPE_SHOW,
            "hide": xplane_constants.ANIM_TYPE_HIDE,
        }[anim_type]
        if anim_type != "transform":
            dataref.show_hide_v1 = v1
            dataref.show_hide_v2 = v2
        dataref.loop = max(0.0, loop)

    # ---- triangles -----------------------------------------------------------------------
    def _add_run(
        self, run: TrisRun, parent, static: mathutils.Matrix, name: str
    ) -> None:
        state = dict(run.state)
        object_state = {k: v for k, v in state.items() if k in _OBJECT_STATE_KEYS}
        material_state = {k: v for k, v in state.items() if k not in _OBJECT_STATE_KEYS}
        key = (
            id(parent),
            tuple(round(static[i][j], 6) for i in range(4) for j in range(4)),
            run.lod if self.options.all_lods else None,
            tuple(sorted(object_state.items())),
        )
        group = self._groups.get(key)
        if group is None:
            group = _Group(parent, static.copy(), run.lod, object_state, name)
            self._groups[key] = group
        material_key = tuple(sorted(material_state.items()))
        slot = group.material_index.get(material_key)
        if slot is None:
            slot = len(group.materials)
            group.material_index[material_key] = slot
            group.materials.append(self.materials.material_for(material_state))
        group.runs.append((run, slot))

    def _flush_groups(self) -> None:
        for group in self._groups.values():
            mesh_name = self._clean(group.name_hint)
            mesh, triangles = build_mesh(
                mesh_name,
                self.vertices,
                self.indices,
                [(run.offset, run.count, slot) for run, slot in group.runs],
                self.options.scale,
            )
            if mesh is None:
                continue
            for material in group.materials:
                mesh.materials.append(material)
            obj_name = self._object_name(group)
            blender_obj = bpy.data.objects.new(obj_name, mesh)
            self.collection.objects.link(blender_obj)
            blender_obj.parent = group.parent
            blender_obj.matrix_basis = T.matrix_to_blender(group.matrix_xp)
            if group.parent is not None and group.parent.name in self._hidden:
                self._hide(blender_obj)
            self._flag_lod(blender_obj, group.lod)
            try:
                self._apply_object_state(blender_obj, group)
            except (ValueError, IndexError, TypeError) as e:
                self.report.warn(
                    f"{self.stem}: could not apply some settings of '{blender_obj.name}' ({e})"
                )
            if all(m.xplane.draw is False for m in group.materials):
                blender_obj.display_type = "WIRE"
                blender_obj.hide_render = True
            self.objects.append(blender_obj)
            self.report.objects_imported += 1
            self.report.meshes_imported += 1
            self.report.triangles_imported += triangles

    def _object_name(self, group: _Group) -> str:
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
    def _apply_object_state(self, blender_obj: bpy.types.Object, group: _Group) -> None:
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
        valid_types = {item[0] for item in m.get_manip_types_for_this_version(None)}
        if kind == "none" or kind not in _MANIP_ARGS:
            self.report.warn(f"{self.stem}: manipulator type '{kind}' is not supported")
            return
        if kind not in valid_types:
            # The scene's X-Plane version might be too old for it
            self.report.warn(
                f"{self.stem}: manipulator '{kind}' needs a newer X-Plane version setting"
            )
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
    def _setup_layer(self) -> None:
        obj = self.obj
        collection = self.collection
        collection.xplane.is_exportable_collection = self.options.make_exportable
        layer = collection.xplane.layer
        layer.name = self.stem
        layer.export_type = (
            xplane_constants.EXPORT_TYPE_COCKPIT
            if self.has_manipulators
            else xplane_constants.EXPORT_TYPE_AIRCRAFT
        )
        if self.options.all_lods and len(obj.lods) >= 2:
            layer.lods = str(min(len(obj.lods), 4))
            for bucket, (near, far) in zip(layer.lod, obj.lods[:4]):
                bucket.near, bucket.far = int(near), int(far)
        manager = self.materials
        for attribute, path in (
            ("texture", manager.diffuse_path),
            ("texture_lit", manager.lit_path),
        ):
            if path:
                setattr(layer, attribute, path)
        if obj.texture_normal and manager.normal_path:
            layer.texture_normal = manager.normal_path
        for kind, attribute in (
            ("normal", "texture_map_normal"),
            ("material_gloss", "texture_map_material_gloss"),
            ("gloss", "texture_map_gloss"),
        ):
            if kind in obj.texture_maps:
                found = self.resolver.resolve(obj.texture_maps[kind])
                if found:
                    setattr(layer, attribute, found)
        if obj.has_normal_metalness:
            layer.normal_metalness = True
        if "GLOBAL_cockpit_lit" in obj.globals and hasattr(layer, "cockpit_lit"):
            layer.cockpit_lit = True
        if "BLEND_GLASS" in obj.globals:
            layer.blend_glass = True
        for directive, entries in obj.globals.items():
            if directive in (
                "GLOBAL_cockpit_lit",
                "BLEND_GLASS",
                "NORMAL_METALNESS",
                "GLOBAL_specular",
                "TEXTURE_NORMAL_RATIO",
                "PARTICLE_SYSTEM",
            ):
                continue
            for args in entries:
                attribute = layer.customAttributes.add()
                attribute.name = directive
                attribute.value = " ".join(args)
        if "PARTICLE_SYSTEM" in obj.globals and obj.globals["PARTICLE_SYSTEM"][0]:
            found = (
                self.resolver.resolve(obj.globals["PARTICLE_SYSTEM"][0][0])
                or obj.globals["PARTICLE_SYSTEM"][0][0]
            )
            layer.particle_system_file = found
        # ATTR_cockpit, _lit_only and _region are one setting for the whole object in the add-on
        used = {key for run in self.obj.iter_tris() for key, _ in run.state}
        if "cockpit_lit_only" in used:
            layer.cockpit_panel_mode = xplane_constants.PANEL_COCKPIT_LIT_ONLY
        elif any(
            dict(run.state).get("cockpit", ("",))[0] == "region"
            for run in self.obj.iter_tris()
        ):
            layer.cockpit_panel_mode = xplane_constants.PANEL_COCKPIT_REGION
        scene = bpy.context.scene
        # The OBJs share their vertices, the exporter only does that when it is told to
        scene.xplane.optimize = True
        # Whatever X-Plane version the OBJ was made for, it is exported for X-Plane 12
        scene.xplane.version = xplane_xp12.LATEST_VERSION
