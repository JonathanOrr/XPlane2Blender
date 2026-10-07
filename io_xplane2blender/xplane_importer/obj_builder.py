"""Builds the Blender data for one parsed OBJ"""

import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import bpy
import mathutils

from io_xplane2blender import xplane_constants, xplane_helpers

from . import transforms as T
from .common import ImportOptions, ImportReport
from .decals import apply_decals
from .defaults import nearest_key_index, show_hide_visible
from .materials import MaterialFactory
from .textures import TextureResolver
from .mesh_builder import build_mesh
from .obj_builder_parts import PartsBuilder
from .obj_parser import AnimNode, AnimOp, Extra, Light, ObjFile, TrisRun

# State keys that belong to the Blender object, the rest belong to the material
_OBJECT_STATE_KEYS = {"manip", "manip_extras", "manip_detents", "light_level"}


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


class ObjBuilder(PartsBuilder):
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
        if "BLEND_GLASS" in obj.globals:
            layer.blend_glass = True
        decals = apply_decals(layer, obj, lambda path: self.resolver.resolve(path) or path)
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
                if (directive, tuple(args)) in decals:
                    continue
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
