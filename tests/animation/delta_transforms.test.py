"""
Keyed delta transforms (Object > Transform > Delta Transform): X-Plane puts every corner where Blender shows it, at
each key and between keys where X-Plane can follow Blender exactly
"""

import math

import bpy
import numpy as np
from mathutils import Quaternion, Vector

from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.obj_evaluator import corners_from_text, max_distance
from io_xplane2blender.xplane_constants import ANIM_TYPE_TRANSFORM, EXPORT_TYPE_AIRCRAFT
from io_xplane2blender.xplane_helpers import get_action_fcurves

DATAREF = "a321/test/ratio"


def blender_corners(obj) -> np.ndarray:
    mesh = obj.data
    mesh.calc_loop_triangles()
    world = obj.matrix_world
    points = [world @ mesh.vertices[v].co for tri in mesh.loop_triangles for v in tri.vertices]
    return np.array([(p.x, p.z, -p.y) for p in points])


class TestDeltaTransforms(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        bpy.ops.wm.read_homefile(use_empty=True)
        self.root = test_creation_helpers.create_datablock_collection("Deltas")
        self.root.xplane.layer.export_type = EXPORT_TYPE_AIRCRAFT

    def part(self, mode="XYZ"):
        """A cube on a turned panel, itself turned on it"""
        panel = bpy.data.objects.new("Panel", None)
        self.root.objects.link(panel)
        panel.location, panel.rotation_euler = (0.3, -2.0, 1.1), (math.radians(-35), 0, math.radians(10))
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "Part", collection=self.root)
        )
        obj.parent = panel
        obj.scale = (0.02, 0.01, 0.005)
        obj.location = (0.05, 0.1, 0.02)
        obj.rotation_mode = mode
        if mode == "QUATERNION":
            obj.rotation_quaternion = Quaternion((0.3, 0.2, 1.0), 0.6)
        else:
            obj.rotation_euler = (0.4, 0.0, 0.7)
        return obj

    def key(self, obj, keys):
        """keys: (frame, dataref value, {path: value})"""
        dataref = obj.xplane.datarefs.add()
        dataref.path, dataref.anim_type = DATAREF, ANIM_TYPE_TRANSFORM
        for frame, value, poses in keys:
            dataref.value = value
            obj.keyframe_insert("xplane.datarefs[0].value", frame=frame)
            for path, pose in poses.items():
                setattr(obj, path, pose)
                obj.keyframe_insert(path, frame=frame)
        for fcurve in get_action_fcurves(obj):
            for key in fcurve.keyframe_points:
                key.interpolation = "LINEAR"

    def assert_same_places(self, obj, checks):
        """checks: (frame, dataref value)"""
        out = self.exportExportableRoot(self.root)
        self.assertLoggerErrors(0)
        for frame, value in checks:
            bpy.context.scene.frame_set(frame)
            distance = max_distance(blender_corners(obj), corners_from_text(out, {DATAREF: value}))
            self.assertLess(distance, 1e-4, f"frame {frame}\n{out}")
        return out

    def test_a_button_pressed_by_its_delta_location(self) -> None:
        obj = self.part()
        pressed = obj.rotation_euler.to_quaternion() @ Vector((0, 0, -0.004))  # along its own -Z
        self.key(obj, ((1, 0.0, {"delta_location": (0, 0, 0)}), (11, 1.0, {"delta_location": pressed})))
        out = self.assert_same_places(obj, ((1, 0.0), (6, 0.5), (11, 1.0)))
        self.assertEqual(1, out.count("ANIM_trans_begin"))
        self.assertNotIn("ANIM_rotate_begin", out)

    def test_a_delta_location_kept_still_adds_to_keyed_location(self) -> None:
        obj = self.part()
        obj.delta_location = (0.01, -0.02, 0.03)
        self.key(obj, ((1, 0.0, {"location": (0.05, 0.1, 0.02)}), (11, 1.0, {"location": (0.05, 0.1, 0.01)})))
        self.assert_same_places(obj, ((1, 0.0), (6, 0.5), (11, 1.0)))

    def test_a_still_delta_rotation_turns_before_the_keys(self) -> None:
        obj = self.part()
        obj.delta_rotation_euler = (0.3, 0.2, 0.1)
        self.key(
            obj,
            (
                (1, 0.0, {"rotation_euler": (0.4, 0, 0.7), "location": (0.05, 0.1, 0.02)}),
                (11, 1.0, {"rotation_euler": (0.4 + math.radians(90), 0, 0.7), "location": (0.05, 0.12, 0.02)}),
            ),
        )
        self.assert_same_places(obj, ((1, 0.0), (11, 1.0)))

    def test_a_knob_turned_by_its_delta_rotation(self) -> None:
        obj = self.part()
        self.key(obj, ((1, 0.0, {"delta_rotation_euler": (0, 0, 0)}), (11, 1.0, {"delta_rotation_euler": (0, 0, math.radians(90))})))
        out = self.assert_same_places(obj, ((1, 0.0), (6, 0.5), (11, 1.0)))
        self.assertEqual(1, out.count("ANIM_rotate_begin"), out)

    def test_a_quaternion_delta_rotation(self) -> None:
        obj = self.part("QUATERNION")
        turned = Quaternion((0, 1, 0), math.radians(60))
        self.key(obj, ((1, 0.0, {"delta_rotation_quaternion": Quaternion()}), (11, 1.0, {"delta_rotation_quaternion": turned})))
        self.assert_same_places(obj, ((1, 0.0), (6, 0.5), (11, 1.0)))

    def test_delta_rotation_and_rotation_both_keyed(self) -> None:
        obj = self.part()
        self.key(
            obj,
            (
                (1, 0.0, {"delta_rotation_euler": (0, 0, 0), "rotation_euler": (0.4, 0, 0.7)}),
                (11, 1.0, {"delta_rotation_euler": (0, 0, 0.8), "rotation_euler": (0.9, 0, 0.7)}),
            ),
        )
        self.assert_same_places(obj, ((1, 0.0), (11, 1.0)))


runTestCases([TestDeltaTransforms])
