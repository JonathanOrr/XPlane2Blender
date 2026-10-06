"""
Checks that animated and static bone hierarchies are exported at the same place Blender puts them.

Each scene is exported, then the OBJ's nested ANIM blocks are evaluated by hand
(static transforms, then each rotation at the dataref's value) and the resulting center of
every mesh is compared against its evaluated world position in Blender.
This covers meshes parented to bones of rotated and moved armatures, armatures under static and
animated parents (#127, #199), and nested bones with different dataref ranges (#242, #190).
"""
import math
import os
from typing import Dict, List, Tuple

import bpy
import numpy as np
from mathutils import Euler, Vector

from io_xplane2blender.tests import *
from io_xplane2blender.tests.test_creation_helpers import *
from io_xplane2blender.xplane_types import xplane_file

__dirname__ = os.path.dirname(__file__)

TOLERANCE = 1e-3


def _rotation(axis: List[float], degrees: float) -> np.ndarray:
    axis = np.array(axis, float)
    length = np.linalg.norm(axis)
    if length == 0:
        return np.eye(4)
    x, y, z = axis / length
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    matrix = np.eye(4)
    matrix[:3, :3] = [
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ]
    return matrix


def _translation(vector: List[float]) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = vector
    return matrix


def _interpolate(keys: List[Tuple[float, float]], value: float) -> float:
    keys = sorted(keys)
    if value <= keys[0][0]:
        return keys[0][1]
    for (v0, a0), (v1, a1) in zip(keys, keys[1:]):
        if v0 <= value <= v1:
            return a0 + (a1 - a0) * (value - v0) / (v1 - v0)
    return keys[-1][1]


def evaluate_obj(text: str, dataref_values: Dict[str, float]) -> Dict[str, List[float]]:
    """
    Returns the center (in X-Plane coordinates) of each mesh's triangle corners,
    after applying the nested ANIM blocks with the given dataref values.
    Needs the exporter's debug comments, which name each mesh before its TRIS.
    """
    vertices, indices, stack = [], [], [np.eye(4)]
    mesh_name, dataref, axis, keys = None, None, None, []
    centers = {}
    for line in text.split("\n"):
        parts = line.split()
        if not parts:
            continue
        command = parts[0]
        if command == "VT":
            vertices.append([float(v) for v in parts[1:4]])
        elif command == "IDX":
            indices.append(int(parts[1]))
        elif command == "IDX10":
            indices.extend(int(v) for v in parts[1:])
        elif command == "#" and len(parts) > 3 and parts[2] == "Mesh:":
            mesh_name = parts[3]
        elif command == "ANIM_begin":
            stack.append(stack[-1].copy())
        elif command == "ANIM_end":
            stack.pop()
        elif command == "ANIM_trans":
            assert parts[1:4] == parts[4:7], "Only static translations are supported"
            stack[-1] = stack[-1] @ _translation([float(v) for v in parts[1:4]])
        elif command == "ANIM_rotate":
            stack[-1] = stack[-1] @ _rotation(
                [float(v) for v in parts[1:4]], float(parts[4])
            )
        elif command == "ANIM_rotate_begin":
            axis = [float(v) for v in parts[1:4]]
            dataref, keys = parts[4], []
        elif command == "ANIM_rotate_key":
            keys.append((float(parts[1]), float(parts[2])))
        elif command == "ANIM_rotate_end":
            stack[-1] = stack[-1] @ _rotation(
                axis, _interpolate(keys, dataref_values[dataref])
            )
        elif command.startswith("ANIM_"):
            raise AssertionError(f"Unsupported command in test: {line}")
        elif command == "TRIS":
            start, count = int(parts[1]), int(parts[2])
            points = [
                (stack[-1] @ np.array(vertices[i] + [1.0]))[:3]
                for i in indices[start : start + count]
            ]
            centers[mesh_name] = [float(c) for c in np.mean(points, axis=0)]
    return centers


def blender_centers(frame: int) -> Dict[str, List[float]]:
    """Center of each mesh's triangle corners in Blender's world, as X-Plane coordinates"""
    bpy.context.scene.frame_set(frame)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    centers = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        mesh.calc_loop_triangles()
        points = [
            evaluated.matrix_world @ mesh.vertices[i].co
            for tri in mesh.loop_triangles
            for i in tri.vertices
        ]
        center = sum(points, Vector()) / len(points)
        centers[obj.name] = [center.x, center.z, -center.y]
    return centers


def _keyframes(path: str, end_value: float, end_rotation: Tuple[float, float, float]):
    return (
        KeyframeInfo(
            idx=1, dataref_path=path, dataref_value=0.0, rotation=(0.0, 0.0, 0.0)
        ),
        KeyframeInfo(
            idx=2, dataref_path=path, dataref_value=end_value, rotation=end_rotation
        ),
    )


class TestBoneWorldPositions(XPlaneTestCase):
    def _build_scene(
        self,
        armature_location,
        armature_rotation,
        parent_empty,
        bone_rotations: Dict[str, Tuple[float, Tuple[float, float, float]]],
    ) -> Dict[str, float]:
        """
        Makes an armature with bones b0 (up) and b1 (sideways, child of b0) with a mesh on each,
        returning the dataref values at the last keyframe.
        parent_empty is None, or (is_animated, location, rotation)
        bone_rotations maps a bone name to its (dataref end value, end rotation in degrees)
        """
        create_initial_test_setup()
        set_xplane_layer(0, {"export_type": "cockpit"})
        bpy.data.collections[0].xplane.is_exportable_collection = True
        bpy.context.scene.xplane.debug = True

        end_values = {}
        parent_info = None
        if parent_empty:
            animated, location, rotation = parent_empty
            empty = create_datablock_empty(
                DatablockInfo(
                    "EMPTY",
                    name="Parent",
                    collection="Layer 1",
                    location=Vector(location),
                )
            )
            empty.rotation_euler = Euler(rotation)
            if animated:
                set_animation_data(empty, _keyframes("sim/test/parent", 1.0, (0, 0, 25)))
                end_values["sim/test/parent"] = 1.0
            parent_info = ParentInfo(empty, "OBJECT")

        arm = create_datablock_armature(
            DatablockInfo(
                "ARMATURE",
                name="Arm",
                collection="Layer 1",
                location=Vector(armature_location),
                parent_info=parent_info,
            ),
            extra_bones=[
                BoneInfo("b0", Vector((0, 0, 0)), Vector((0, 0, 2)), ""),
                BoneInfo("b1", Vector((0, 0, 2)), Vector((1, 0, 2)), "b0"),
            ],
        )
        arm.rotation_euler = Euler(armature_rotation)
        # create_datablock_armature doesn't link into DatablockInfo.collection
        for collection in list(arm.users_collection):
            collection.objects.unlink(arm)
        bpy.data.collections["Layer 1"].objects.link(arm)

        create_datablock_mesh(
            DatablockInfo(
                "MESH",
                name="M0",
                collection="Layer 1",
                location=Vector((1, 0, 1)),
                parent_info=ParentInfo(arm, "BONE", "b0"),
            )
        )
        create_datablock_mesh(
            DatablockInfo(
                "MESH",
                name="M1",
                collection="Layer 1",
                location=Vector((0.5, 1, 0.3)),
                parent_info=ParentInfo(arm, "BONE", "b1"),
            )
        )
        for bone_name, (end_value, rotation) in bone_rotations.items():
            path = f"sim/test/{bone_name}"
            set_animation_data(
                arm.pose.bones[bone_name], _keyframes(path, end_value, rotation), arm
            )
            end_values[path] = end_value
        return end_values

    def _assert_matches_blender(self, end_values: Dict[str, float]) -> None:
        text = xplane_file.createFileFromBlenderRootObject(
            bpy.data.collections["Layer 1"], bpy.context.scene.view_layers[0]
        ).write()
        self.assertLoggerErrors(0)

        # Every dataref at its first keyframe (frame 1) and at its last (frame 2)
        at_start = {path: 0.0 for path in end_values}
        for frame, values in ((1, at_start), (2, end_values)):
            actual = evaluate_obj(text, values)
            expected = blender_centers(frame)
            self.assertEqual(sorted(actual), sorted(expected))
            for name, center in expected.items():
                for axis in range(3):
                    self.assertAlmostEqual(
                        actual[name][axis],
                        center[axis],
                        delta=TOLERANCE,
                        msg=f"{name} on axis {axis} at frame {frame}: "
                        f"exported {actual[name]}, Blender {center}",
                    )

    def test_static_bones(self) -> None:
        self._assert_matches_blender(self._build_scene((0, 0, 0), (0, 0, 0), None, {}))

    def test_animated_root_bone(self) -> None:
        self._assert_matches_blender(
            self._build_scene((0, 0, 0), (0, 0, 0), None, {"b0": (1.0, (0, 0, 40))})
        )

    def test_animated_child_bone_only(self) -> None:
        for rotation in ((30, 0, 0), (0, 30, 0), (0, 0, 30)):
            with self.subTest(rotation=rotation):
                self._assert_matches_blender(
                    self._build_scene((0, 0, 0), (0, 0, 0), None, {"b1": (1.0, rotation)})
                )

    def test_nested_bones_with_different_dataref_ranges(self) -> None:
        # Upstream #242 and #190: the child's keys must use the child's dataref range
        self._assert_matches_blender(
            self._build_scene(
                (0, 0, 0),
                (0, 0, 0),
                None,
                {"b0": (360.0, (0, 0, 40)), "b1": (45.0, (30, 0, 0))},
            )
        )

    def test_moved_and_rotated_armature(self) -> None:
        # Upstream #127: the armature's own static transform
        for bone_rotations in ({}, {"b0": (1.0, (0, 0, 40)), "b1": (1.0, (30, 0, 0))}):
            with self.subTest(animated=bool(bone_rotations)):
                self._assert_matches_blender(
                    self._build_scene(
                        (1, 2, 3), (0.3, 0.5, 0.2), None, bone_rotations
                    )
                )

    def test_armature_under_static_parent(self) -> None:
        for bone_rotations in ({}, {"b0": (1.0, (0, 0, 40)), "b1": (1.0, (30, 0, 0))}):
            with self.subTest(animated=bool(bone_rotations)):
                self._assert_matches_blender(
                    self._build_scene(
                        (1, 2, 3),
                        (0.3, 0.5, 0.2),
                        (False, (4, -1, 2), (0.2, 0.7, -0.4)),
                        bone_rotations,
                    )
                )

    def test_armature_under_animated_parent(self) -> None:
        for bone_rotations in ({}, {"b0": (1.0, (0, 0, 40)), "b1": (1.0, (30, 0, 0))}):
            with self.subTest(animated=bool(bone_rotations)):
                self._assert_matches_blender(
                    self._build_scene(
                        (1, 2, 3),
                        (0.3, 0.5, 0.2),
                        (True, (4, -1, 2), (0.2, 0.7, -0.4)),
                        bone_rotations,
                    )
                )


runTestCases([TestBoneWorldPositions])
