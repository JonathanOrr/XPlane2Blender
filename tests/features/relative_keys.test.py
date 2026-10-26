"""
Relative keys: movement keyed on the delta location, so a part can be moved without its keys pulling it back.
Make Keys Relative, Key Pose and the motion overlay
"""

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.viewport.motion import SLIDE, motion_of
from io_xplane2blender.xplane_helpers import get_action_fcurves


def paths(obj):
    return sorted({fc.data_path for fc in get_action_fcurves(obj) if not fc.data_path.startswith("xplane")})


def travel(out: str):
    """How far each ANIM_trans_key is from the first. The keys themselves include where the part stands"""
    keys = [[float(v) for v in l.split()[2:]] for l in out.splitlines() if "ANIM_trans_key" in l]
    return [[round(v - f, 6) for v, f in zip(key, keys[0])] for key in keys]


def select(*objects) -> None:
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


class TestRelativeKeys(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        self.root = test_creation_helpers.create_datablock_collection("Panel")
        self.root.xplane.layer.export_type = C.EXPORT_TYPE_COCKPIT

    def mesh(self, name, location=(0.1, -2.0, 1.0)):
        return test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", name, collection=self.root, location=Vector(location))
        )

    def key_by_location(self, obj, travel=(0, 0, -0.002)):
        """A button keyed the old way: absolute locations"""
        dataref = obj.xplane.datarefs.add()
        dataref.path, dataref.anim_type = f"CMND=a321/{obj.name}", C.ANIM_TYPE_TRANSFORM
        start = obj.location.copy()
        for frame, value, offset in ((1, 0.0, Vector()), (5, 1.0, Vector(travel))):
            dataref.value = value
            obj.keyframe_insert("xplane.datarefs[0].value", frame=frame)
            obj.location = start + offset
            obj.keyframe_insert("location", frame=frame)
        bpy.context.scene.frame_set(1)

    def export(self) -> str:
        test_creation_helpers.make_root_exportable(self.root)
        out = self.exportExportableRoot(self.root)
        self.assertLoggerErrors(0)
        return out

    def test_make_keys_relative_keeps_the_obj(self) -> None:
        obj = self.mesh("apu_start")
        self.key_by_location(obj)
        before = self.export()
        select(obj)

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.make_keys_relative())

        self.assertEqual(["delta_location"], paths(obj))
        self.assertEqual(Vector((0.1, -2.0, 1.0)), obj.location)
        self.assertEqual(before, self.export())

    def test_a_relative_button_can_be_moved(self) -> None:
        obj = self.mesh("apu_start")
        self.key_by_location(obj)
        select(obj)
        bpy.ops.xplane.make_keys_relative()
        before = self.export()

        obj.location.x += 0.5
        bpy.context.scene.frame_set(5)

        self.assertAlmostEqual(0.6, obj.matrix_world.translation.x, places=5)
        self.assertAlmostEqual(0.998, obj.matrix_world.translation.z, places=5)
        self.assertEqual([[0, 0, 0], [0, -0.002, 0]], travel(before))
        self.assertEqual(travel(before), travel(self.export()))

    def test_shared_keys_are_made_relative_once_for_every_part(self) -> None:
        first, second = self.mesh("a"), self.mesh("b")
        self.key_by_location(first)
        second.animation_data_create().action = first.animation_data.action
        if hasattr(second.animation_data, "action_slot"):
            second.animation_data.action_slot = first.animation_data.action_slot
        select(first, second)

        bpy.ops.xplane.make_keys_relative()

        self.assertEqual(["delta_location"], paths(second))
        self.assertEqual(first.location, second.location)

    def test_a_still_delta_location_is_kept(self) -> None:
        obj = self.mesh("seat")
        obj.delta_location = (0, 0.25, 0)
        self.key_by_location(obj)
        before = self.export()
        select(obj)

        bpy.ops.xplane.make_keys_relative()

        self.assertEqual(before, self.export())

    def test_key_pose_keys_the_delta_location_of_a_relative_part(self) -> None:
        obj = self.mesh("apu_start")
        self.key_by_location(obj)
        select(obj)
        bpy.ops.xplane.make_keys_relative()
        bpy.context.scene.frame_set(9)
        obj.xplane.datarefs[0].value = 2.0
        obj.delta_location = (0, 0, -0.003)

        bpy.ops.xplane.key_pose(index=0)

        self.assertEqual(["delta_location"], paths(obj))
        self.assertEqual([[0, 0, 0], [0, -0.002, 0], [0, -0.003, 0]], travel(self.export()))

    def test_the_overlay_reads_a_slide_on_the_delta_location(self) -> None:
        obj = self.mesh("apu_start")
        self.key_by_location(obj, travel=(0.01, 0, 0))
        select(obj)
        bpy.ops.xplane.make_keys_relative()

        motion = motion_of(obj)

        self.assertEqual(SLIDE, motion.kind)
        self.assertAlmostEqual(0.01, motion.travel[-1], places=6)
        self.assertLess((motion.origin - Vector((0.1, -2.0, 1.0))).length, 1e-6)


runTestCases([TestRelativeKeys])
