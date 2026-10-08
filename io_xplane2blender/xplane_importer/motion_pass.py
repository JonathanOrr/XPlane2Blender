"""
Takes the Empties out of an imported object where the part can carry its own animation.

The builder makes an Empty for every ANIM block and a mesh below it. In Blender the part is the object that moves:
the pivot is its origin and the dataref is on it, as the exporter reads it. So the mesh below a lone animation takes
its place, a chain of animations of one dataref becomes one object, and a show / hide that holds a single thing goes
on that thing. What stays an Empty holds several things, or is a different dataref, or a static frame.
"""

import collections
from typing import Callable, Dict, List

import bpy
import mathutils

from io_xplane2blender.xplane_constants import (
    EMPTY_USAGE_NONE,
    MANIP_DRAG_AXIS,
    MANIP_DRAG_AXIS_DETENT,
    MANIP_DRAG_ROTATE,
    MANIP_DRAG_ROTATE_DETENT,
)

from . import motion as M
from . import transforms as T


class MotionPass:
    def __init__(
        self,
        objects: List[bpy.types.Object],
        motions: Dict[bpy.types.Object, M.Motion],
        holders: List[bpy.types.Object],
        frames: List[bpy.types.Object],
        names: Dict[bpy.types.Object, str],
        exact: Dict[bpy.types.Object, mathutils.Matrix],
        unnamed: set,
    ) -> None:
        self.objects = objects
        self.motions = motions
        self.holders = holders
        self.frames = frames
        # What a part is called when it takes the place of the Empty of its animation
        self.names = names
        # Where the objects are, as the numbers they were made from. A turn that is nearly straight up (an Euler
        # angle of 90 degrees) comes back from Blender's own rotation with an error that Blender 3.6 makes visible
        self.exact = exact
        self.unnamed = unnamed
        self.renames = []
        self.kids = collections.defaultdict(list)
        for obj in objects:
            if obj.parent is not None:
                self.kids[obj.parent].append(obj)
        self.removed: List[bpy.types.Object] = []
        self.gone = set()
        self.pruned = 0

    def run(self) -> int:
        """Returns how many Empties were taken out"""
        self._prune()
        for holder in self.holders:
            self._carry_visibility(holder)
        self._fold_frames()
        for obj in list(self.motions):
            if obj in self.motions:
                self._join_chain(obj)
                self._carry_mesh(obj)
                if obj in self.motions:
                    self._split_leaves(obj)
        self._fold_frames()
        self.objects[:] = [o for o in self.objects if o not in self.gone]
        for obj in self.removed:
            bpy.data.objects.remove(obj)
        for obj, name in self.renames:
            obj.name = name
        return len(self.removed)

    def _prune(self) -> None:
        """An animation, frame or show / hide with nothing in it draws nothing and moves nothing"""
        for obj in reversed(list(self.objects)):
            if (
                obj.type != "EMPTY"
                or self.kids.get(obj)
                or obj.xplane.special_empty_props.special_type != EMPTY_USAGE_NONE
            ):
                continue
            if obj.parent is not None:
                self.kids[obj.parent].remove(obj)
            self.motions.pop(obj, None)
            self.removed.append(obj)
            self.gone.add(obj)
            self.pruned += 1

    def _only_child(self, obj: bpy.types.Object):
        kids = self.kids.get(obj, [])
        return kids[0] if len(kids) == 1 else None

    def _basis(self, obj: bpy.types.Object) -> mathutils.Matrix:
        return self.exact.get(obj, obj.matrix_basis).copy()

    def _place(self, obj: bpy.types.Object, matrix: mathutils.Matrix) -> None:
        self.exact[obj] = matrix.copy()
        obj.matrix_basis = matrix

    @staticmethod
    def _move_datarefs(source: bpy.types.Object, target: bpy.types.Object) -> None:
        for dataref in source.xplane.datarefs:
            copy = target.xplane.datarefs.add()
            for name in ("path", "anim_type", "show_hide_v1", "show_hide_v2", "loop"):
                setattr(copy, name, getattr(dataref, name))

    def _remove(self, obj: bpy.types.Object, replacement) -> None:
        """obj goes, and the object that takes its place under its parent is replacement"""
        self._move_datarefs(obj, replacement)
        parent = obj.parent
        replacement.parent = parent
        if parent is not None:
            self.kids[parent].remove(obj)
            self.kids[parent].append(replacement)
        self.kids[obj] = []
        self.removed.append(obj)
        self.gone.add(obj)

    # ---- one dataref, one object ---------------------------------------------------------
    def _join_chain(self, outer: bpy.types.Object) -> None:
        """Animations of one dataref that follow each other: the inner Empty goes into the outer one"""
        while True:
            inner = self._only_child(outer)
            if inner is None or inner not in self.motions:
                return
            if T.has_rotation(self._basis(outer)) or T.has_rotation(self._basis(inner)):
                return
            joined = M.combine(
                self.motions[outer],
                self.motions[inner],
                self._basis(inner).to_translation(),
            )
            if joined is None:
                return
            self.motions[outer] = joined
            del self.motions[inner]
            self._move_datarefs(inner, outer)
            self.kids[outer] = self.kids.pop(inner, [])
            for kid in self.kids[outer]:
                kid.parent = outer
            self.removed.append(inner)
            self.gone.add(inner)

    def _main_part(self, obj: bpy.types.Object, identity: bool):
        """
        The mesh among the children of obj that can stand in for it, the one with the most vertices. The others
        are then its children, so it must not have a show / hide, LODs or a light level of its own. It must sit at the origin of obj when what it stands in for is not turned about its
        pivot (a turn takes what sits beside the pivot into the shape of the mesh, and leaves the others where they are)
        """
        kids = self.kids.get(obj, [])
        parts = [
            kid
            for kid in kids
            if kid.type == "MESH"
            and kid not in self.motions
            and not self._passes_down(kid, [k for k in kids if k is not kid])
            and not self._must_be_leaf(kid)
            and (not identity or T.is_identity(self._basis(kid)))
        ]
        return max(parts, key=lambda m: len(m.data.vertices)) if parts else None

    @staticmethod
    def _must_be_leaf(obj: bpy.types.Object) -> bool:
        """The exporter writes drag axis and drag rotate click zones only on objects with no children"""
        manip = obj.xplane.manip
        return manip.enabled and manip.type in (
            MANIP_DRAG_AXIS,
            MANIP_DRAG_AXIS_DETENT,
            MANIP_DRAG_ROTATE,
            MANIP_DRAG_ROTATE_DETENT,
        )

    def _drags_below(self, obj: bpy.types.Object) -> bool:
        return self._must_be_leaf(obj) or any(
            self._drags_below(kid) for kid in self.kids.get(obj, [])
        )

    @staticmethod
    def _passes_down(obj: bpy.types.Object, others: List[bpy.types.Object]) -> bool:
        """
        Show / hide lines, LODs and the light level of an object go on to its children, so it can not take on others.
        A light level only goes on to children that have none of their own
        """
        x = obj.xplane
        if x.datarefs or x.override_lods:
            return True
        return x.lightLevel and not all(
            other.type == "MESH" and other.xplane.lightLevel for other in others
        )

    def _adopt(self, parent: bpy.types.Object, kids: List[bpy.types.Object]) -> None:
        for kid in kids:
            kid.parent = parent
        self.kids[parent].extend(kids)

    def _static_below(self, empty: bpy.types.Object):
        """The mesh that is alone below an animation, and its place, through the static frames between"""
        placed = mathutils.Matrix.Identity(4)
        between = []
        thing = self._only_child(empty)
        while (
            thing is not None
            and thing.type == "EMPTY"
            and thing not in self.motions
            and not thing.xplane.datarefs
        ):
            placed = placed @ self._basis(thing)
            between.append(thing)
            thing = self._only_child(thing)
        if thing is None or thing.type != "MESH" or thing in self.motions:
            return None, placed, between
        return thing, placed @ self._basis(thing), between

    def _carry_mesh(self, empty: bpy.types.Object) -> None:
        """A mesh that is alone below an animation is the animated object"""
        mesh, placed, between = self._static_below(empty)
        others = []
        if mesh is None:
            mesh = self._main_part(empty, identity=not self.motions[empty].spins)
            if mesh is None:
                return
            placed, others = self._basis(mesh), [
                k for k in self.kids[empty] if k is not mesh
            ]
        motion = self.motions[empty]
        if motion.spins:
            # Turning takes the part about the pivot, so what sits beside the pivot is part of its shape
            if not T.is_identity(placed):
                mesh.data.transform(placed)
            self._place(mesh, self._basis(empty))
        else:
            # Moving takes the part with it: its turn stays where it is and its place is moved with every key
            placed = self._basis(empty).to_3x3().to_4x4() @ placed
            M.shifted(motion, placed.to_translation())
            self._place(mesh, placed.to_3x3().to_4x4())
        self.motions[mesh] = self.motions.pop(empty)
        if empty in self.names and mesh in self.unnamed:
            self.renames.append((mesh, self.names[empty]))
        self._remove(empty, mesh)
        self._adopt(mesh, others)
        for frame in between:
            self.kids.pop(frame, None)
            self.removed.append(frame)
            self.gone.add(frame)

    def _split_leaves(self, empty: bpy.types.Object) -> None:
        """
        A drag click zone must have no children and take its motion from its own animation, so where an animation
        holds it and other parts (the Citation's throttles), the zone gets a copy of the animation beside the Empty
        """
        kids = self.kids.get(empty, [])
        leaves = [
            k
            for k in kids
            if k.type == "MESH" and k not in self.motions and self._must_be_leaf(k)
        ]
        if len(kids) < 2 or not leaves or empty.xplane.lightLevel:
            return
        motion = self.motions[empty]
        for leaf in leaves:
            placed = self._basis(leaf)
            copy = M.Motion(
                motion.dataref,
                motion.loop,
                list(motion.values),
                list(motion.location) if motion.location else None,
                [M.Spin(s.axis.copy(), list(s.angles)) for s in motion.spins],
            )
            if motion.spins:
                if not T.is_identity(placed):
                    leaf.data.transform(placed)
                basis = self._basis(empty)
            else:
                placed = self._basis(empty).to_3x3().to_4x4() @ placed
                M.shifted(copy, placed.to_translation())
                basis = placed.to_3x3().to_4x4()
            self._move_datarefs(empty, leaf)
            if empty.xplane.override_lods:
                leaf.xplane.override_lods = True
                for i in range(4):
                    leaf.xplane.lod[i] = empty.xplane.lod[i]
            self.kids[empty].remove(leaf)
            leaf.parent = empty.parent
            if empty.parent is not None:
                self.kids[empty.parent].append(leaf)
            self._place(leaf, basis)
            self.motions[leaf] = copy

    # ---- frames --------------------------------------------------------------------------
    def _fold_frames(self) -> None:
        """A frame for one part only is the part's own turn. The frames that panels share stay"""
        for frame in self.frames:
            part = self._only_child(frame)
            if frame in self.gone or part is None:
                continue
            turn = self._basis(frame).to_3x3()
            if self._can_turn(part, turn):
                self._turn(part, turn)
                self._remove(frame, part)

    def _turned_spins(self, motion: M.Motion, turn: mathutils.Matrix) -> List[M.Spin]:
        return [M.Spin(turn @ s.axis, s.angles) for s in motion.spins]

    def _can_turn(self, obj: bpy.types.Object, turn: mathutils.Matrix) -> bool:
        """Whether everything below a static turn can take it: the turn is then no longer between them"""
        if self._drags_below(obj):
            # The exporter writes a drag's axis in the frame its animation turns in, so that frame stays
            return False
        motion = self.motions.get(obj)
        if motion is None or not motion.spins:
            return True
        spins = self._turned_spins(motion, turn)
        if len(spins) > 1 and M.euler_order(spins) is None:
            return False
        # A mesh takes the turn into its vertices, what else is below goes on turning with it
        return obj.type == "MESH" or all(
            self._can_turn(kid, turn) for kid in self.kids.get(obj, [])
        )

    def _turn(self, obj: bpy.types.Object, turn: mathutils.Matrix) -> None:
        """
        Puts a static turn that was above obj into it. Turning, then moving or turning about an axis, is moving
        or turning about the turned axis, and then turning. A move or a turn of the part is a turn of its keys
        """
        motion = self.motions.get(obj)
        if motion is None or not motion.spins:
            if motion is not None:
                M.shifted(motion, None, turn)
            self._place(obj, turn.to_4x4() @ self._basis(obj))
            return
        motion.spins = self._turned_spins(motion, turn)
        M.shifted(motion, None, turn)
        self._place(
            obj, mathutils.Matrix.Translation(turn @ self._basis(obj).to_translation())
        )
        if obj.type == "MESH":
            obj.data.transform(turn.to_4x4())
        else:
            for kid in self.kids.get(obj, []):
                self._turn(kid, turn)

    # ---- show and hide -------------------------------------------------------------------
    def _carry_visibility(self, holder: bpy.types.Object) -> None:
        """An Empty that shows or hides a single thing, or a thing with others at its side: the thing is shown or hidden itself"""
        thing = self._only_child(holder)
        others = []
        if thing is None and self.kids.get(holder) and holder not in self.gone:
            thing = self._main_part(holder, identity=True)
            others = [k for k in self.kids[holder] if k is not thing]
        if thing is None or holder in self.gone:
            return
        place = self._basis(holder)
        if thing in self.motions:
            if T.has_rotation(place):
                return
            shift = place.to_translation()
            motion = self.motions[thing]
            if motion.location:
                M.shifted(motion, shift)
            else:
                self._place(
                    thing, self._basis(thing) @ mathutils.Matrix.Translation(shift)
                )
        else:
            self._place(thing, place @ self._basis(thing))
        self._remove(holder, thing)
        self._adopt(thing, others)


def key_motions(
    motions: Dict[bpy.types.Object, M.Motion],
    add_dataref: Callable[[bpy.types.Object, str, float], object],
) -> None:
    for obj, motion in motions.items():
        M.apply(obj, motion, add_dataref)
