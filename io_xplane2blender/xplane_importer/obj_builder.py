"""Builds the Blender data for one parsed OBJ"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import bpy
import mathutils

from io_xplane2blender import xplane_constants, xplane_display_sizes, xplane_helpers

from . import motion as motions
from . import transforms as T
from .common import ImportOptions, ImportReport
from .decals import apply_decals
from .defaults import show_hide_visible
from .materials import MaterialFactory
from .mesh_builder import build_mesh
from .motion_pass import MotionPass, key_motions
from .obj_builder_parts import PartsBuilder
from .obj_parser import AnimNode, AnimOp, Extra, Light, ObjFile, TrisRun
from .textures import TextureResolver

# State keys that belong to the Blender object, the rest belong to the material
_OBJECT_STATE_KEYS = {
    "manip",
    "manip_extras",
    "manip_detents",
    "light_level",
    "hud_glass",
}


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
        self._motions: Dict[bpy.types.Object, motions.Motion] = {}
        self._frames: Dict[tuple, bpy.types.Object] = {}
        self._holders: List[bpy.types.Object] = []  # the Empties of show and hide lines
        # What a part is called for its animation, and where each object is, as the numbers it was made from
        self._names: Dict[bpy.types.Object, str] = {}
        self._unnamed = set()  # meshes that nothing in the file names
        self._exact: Dict[bpy.types.Object, mathutils.Matrix] = {}
        self._light_count = 0

    # ------------------------------------------------------------------------------------
    def build(self) -> BuiltObj:
        self.collection = bpy.data.collections.new(self.stem)
        (self.parent_collection or bpy.context.scene.collection).children.link(
            self.collection
        )

        self._walk(self.obj.root, None, self.base_matrix, self.stem)
        self._flush_groups()
        self._carry_animations()
        self._fit_empties()
        self._apply_hidden()
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

    def _carry_animations(self) -> None:
        """The parts carry their own animations where they can, then every animation is keyed"""
        if self.options.import_animations:
            carrying = MotionPass(
                self.objects,
                self._motions,
                self._holders,
                list(self._frames.values()),
                self._names,
                self._exact,
                self._unnamed,
            )
            self.report.objects_imported -= carrying.run()
            if carrying.pruned:
                self.report.info(
                    f"{self.stem}: {carrying.pruned} animation(s) with nothing in them were left out"
                )
        key_motions(
            self._motions,
            lambda obj, path, loop: self._add_dataref(
                obj, path, "transform", loop=loop
            ),
        )

    def _fit_empties(self) -> None:
        """An aircraft has thousands of empties, so each is drawn at the size of the parts hanging on it"""
        sizes = xplane_display_sizes.part_sizes(
            o for o in self.objects if o.type == "MESH"
        )
        xplane_display_sizes.fit_empty_sizes(
            (o for o in self.objects if o.type == "EMPTY"), sizes, self.options.scale
        )

    # ---- animation nodes -----------------------------------------------------------------
    def _apply_node_transforms(self, node, parent, static, name):
        """Creates the Empties an ANIM block needs. Returns the parent and the static matrix for its contents"""
        # X-Plane space matrix of everything that is static since the last Empty
        pending = static.copy()
        shows = node.visibility if self.options.import_animations else []
        label = node.comment or name

        if shows:
            # Visibility covers everything in the block, so it goes on the outermost Empty
            parent, pending = self._framed(parent, pending, label)
            holder = self._make_empty(label + " visibility", parent, pending)
            self._holders.append(holder)
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
        # As large as one gets, _fit_empties makes it fit the parts on it
        empty.empty_display_size = xplane_display_sizes.MAX_SIZE * self.options.scale
        self.collection.objects.link(empty)
        empty.parent = parent
        self._exact[empty] = T.matrix_to_blender(matrix_xp)
        empty.matrix_basis = self._exact[empty]
        if parent is not None and parent.name in self._hidden:
            self._hide(empty)
        self.objects.append(empty)
        self.report.objects_imported += 1
        return empty

    def _make_dynamic_empty(
        self, op: AnimOp, parent, pending: mathutils.Matrix, label: str
    ) -> bpy.types.Object:
        """The Empty of an animation. It is keyed once it is known which object carries the animation"""
        name = f"{label} {op.dataref.split('/')[-1]}"
        parent, pending = self._framed(parent, pending, label)
        pending_bl = T.matrix_to_blender(pending)
        if op.kind == "trans":
            # The place of the part is folded into the keys
            motion = motions.from_translation(
                op, pending_bl.to_translation(), self.options.scale
            )
            empty = self._make_empty(name, parent, mathutils.Matrix.Identity(4))
        else:
            motion = motions.from_rotation(op)
            empty = self._make_empty(name, parent, pending)
        self._motions[empty] = motion
        if label == self.stem:
            # Nothing in the file names the part, so its dataref does
            self._names[empty] = empty.name
        self.report.animations_imported += 1
        return empty

    def _framed(self, parent, pending: mathutils.Matrix, label: str):
        """
        A static turn before an animation is the frame the part moves in, an Empty that the parts of a panel share.
        Returns the frame (or the parent) and where the part is in it
        """
        if not T.has_rotation(T.matrix_to_blender(pending)):
            return parent, pending
        turn = pending.to_3x3().to_4x4()
        key = (
            id(parent),
            tuple(round(turn[i][j], 5) for i in range(3) for j in range(3)),
        )
        frame = self._frames.get(key)
        if frame is None:
            frame = self._make_empty(label + " frame", parent, turn)
            self._frames[key] = frame
        return frame, turn.inverted() @ pending

    def _hide(self, obj: bpy.types.Object) -> None:
        """
        Hides what X-Plane does not draw with the datarefs at their default values (with the eye, once it is built,
        because Blender does not move the objects that are disabled in the viewports). It is still exported
        """
        self._hidden.add(obj.name)
        obj.hide_render = True
        obj[xplane_helpers.PREVIEW_HIDDEN] = True

    def _apply_hidden(self) -> None:
        for obj in self.objects:
            if obj.get(xplane_helpers.PREVIEW_HIDDEN):
                obj.hide_set(True)

    def _add_dataref(
        self,
        obj,
        path: str,
        anim_type: str,
        v1: float = 0.0,
        v2: float = 0.0,
        loop: float = 0.0,
    ):
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
        return dataref

    # ---- triangles -----------------------------------------------------------------------
    def _add_run(
        self, run: TrisRun, parent, static: mathutils.Matrix, name: str
    ) -> None:
        state = dict(run.state)
        object_state = {k: v for k, v in state.items() if k in _OBJECT_STATE_KEYS}
        material_state = {k: v for k, v in state.items() if k not in _OBJECT_STATE_KEYS}
        material_key = tuple(sorted(material_state.items()))
        # One material per mesh: the exporter writes an object with the settings of its first material only
        key = (
            id(parent),
            tuple(round(static[i][j], 6) for i in range(4) for j in range(4)),
            run.lod if self.options.all_lods else None,
            tuple(sorted(object_state.items())),
            material_key,
        )
        group = self._groups.get(key)
        if group is None:
            group = _Group(parent, static.copy(), run.lod, object_state, name)
            self._groups[key] = group
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
            if obj_name == self._clean(self.stem):
                self._unnamed.add(blender_obj)
            self.collection.objects.link(blender_obj)
            blender_obj.parent = group.parent
            self._exact[blender_obj] = T.matrix_to_blender(group.matrix_xp)
            blender_obj.matrix_basis = self._exact[blender_obj]
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
        decals = apply_decals(
            layer, obj, lambda path: self.resolver.resolve(path) or path
        )
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
