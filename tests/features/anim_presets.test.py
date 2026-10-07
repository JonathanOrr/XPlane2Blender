"""
Animation presets for cockpit controls: push buttons, switches and knobs keyed in one step, checked through
what the exporter writes
"""

import math
import os

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

__dirname__ = os.path.dirname(__file__)


def mesh(name: str) -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name, collection="Panel")
    )


def select(*objects) -> None:
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def anim_lines(out: str):
    return [line.split() for line in out.splitlines() if line.strip().startswith(("ANIM_", "ATTR_manip"))]


class TestAnimPresets(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        test_creation_helpers.create_datablock_collection("Panel")

    def export(self) -> str:
        root = test_creation_helpers.make_root_exportable("Panel")
        root.xplane.layer.export_type = "cockpit"
        out = self.exportExportableRoot("Panel")
        self.assertFalse(logger.hasErrors(), logger.messagesToString())
        return out

    def assertKeys(self, lines, begin, expected):
        """expected: list of key value lists after the directive name"""
        start = next(i for i, l in enumerate(lines) if l[:2] == begin)
        keys = []
        for line in lines[start + 1 :]:
            if not line[0].endswith("_key"):
                break
            keys.append([float(v) for v in line[1:]])
        self.assertEqual(len(expected), len(keys), lines)
        for want, got in zip(expected, keys):
            for w, g in zip(want, got):
                self.assertAlmostEqual(w, g, places=3, msg=lines)

    def test_push_buttons_use_their_manipulator_command(self) -> None:
        buttons = []
        for name in ("apu_reset", "apu_start"):
            obj = mesh(name)
            obj.xplane.manip.enabled = True
            obj.xplane.manip.type = "command"
            obj.xplane.manip.command = f"a321/apu/{name}"
            buttons.append(obj)
        select(*buttons)

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.anim_push_button(axis="-Z", distance=2.2))

        lines = anim_lines(self.export())
        self.assertKeys(lines, ["ANIM_trans_begin", "CMND=a321/apu/apu_reset"], [[0, 0, 0, 0], [1, 0, -0.0022, 0]])
        self.assertKeys(lines, ["ANIM_trans_begin", "CMND=a321/apu/apu_start"], [[0, 0, 0, 0], [1, 0, -0.0022, 0]])

    def test_a_push_button_without_a_manipulator_becomes_clickable(self) -> None:
        obj = mesh("{weird name}")
        select(obj)
        bpy.ops.xplane.anim_push_button(command="a321/key/{name}", distance=1.0)
        self.assertTrue(obj.xplane.manip.enabled)
        self.assertEqual("a321/key/{weird name}", obj.xplane.manip.command)
        self.assertEqual("button", obj.xplane.manip.cursor)
        self.assertEqual("CMND=a321/key/{weird name}", obj.xplane.datarefs[0].path)

    def test_nothing_to_push_with_leaves_the_object_alone(self) -> None:
        obj = mesh("blank")
        select(obj)
        self.assertEqual({"CANCELLED"}, bpy.ops.xplane.anim_push_button())
        self.assertEqual(0, len(obj.xplane.datarefs))
        self.assertFalse(obj.xplane.manip.enabled)

    def test_switch_positions_turn_around_the_objects_own_axis(self) -> None:
        obj = mesh("elt_switch")
        obj.rotation_euler = (0, 0, math.radians(30))
        select(obj)

        bpy.ops.xplane.anim_switch(
            dataref="a321/misc/elt_pos", positions=3, first_offset=20, offset_step=-20, axis="X"
        )

        lines = anim_lines(self.export())
        # X-Plane keeps the 30 degree yaw, then turns the switch around its own X axis
        self.assertKeys(lines, ["ANIM_rotate_begin", "1"], [[0, 20], [1, 0], [2, -20]])
        self.assertKeys(lines, ["ANIM_rotate_begin", "0"], [[0, 30], [1, 30], [2, 30]])

    def test_moving_follows_the_objects_own_axis(self) -> None:
        obj = mesh("slider")
        obj.rotation_euler = (0, 0, math.radians(90))
        select(obj)

        bpy.ops.xplane.anim_switch(
            dataref="a321/slider", positions=2, motion="MOVE", axis="X", first_offset=0, offset_step=10
        )

        # Local X of an object turned 90 degrees is Blender's +Y, which is X-Plane's -Z
        self.assertKeys(anim_lines(self.export()), ["ANIM_trans_begin", "a321/slider"], [[0, 0, 0, 0], [1, 0, 0, -0.01]])

    def test_endless_knobs_loop(self) -> None:
        obj = mesh("heading_knob")
        select(obj)

        bpy.ops.xplane.anim_range(
            dataref="a321/fcu/hdg", value_from=0, value_to=360, offset_from=0, offset_to=-360, axis="Z", loop=360
        )

        lines = anim_lines(self.export())
        # Whole turns survive: big turns are keyed every 90 degrees, which X-Plane interpolates the same way
        self.assertKeys(lines, ["ANIM_rotate_begin", "0"], [[0, 0], [90, -90], [180, -180], [270, -270], [360, -360]])
        loops = [float(l[1]) for l in lines if l[0] == "ANIM_keyframe_loop"]
        self.assertEqual([360.0], loops)

    def test_animated_objects_are_only_redone_when_asked(self) -> None:
        obj = mesh("knob")
        select(obj)
        bpy.ops.xplane.anim_range(dataref="a321/old")

        self.assertEqual({"CANCELLED"}, bpy.ops.xplane.anim_range(dataref="a321/new"))
        self.assertEqual(["a321/old"], [d.path for d in obj.xplane.datarefs])

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.anim_range(dataref="a321/new", replace=True))
        self.assertEqual(["a321/new"], [d.path for d in obj.xplane.datarefs])
        lines = anim_lines(self.export())
        # From where the knob stood before the first animation, not from the old animation's first position
        self.assertKeys(lines, ["ANIM_rotate_begin", "0"], [[0, -135], [1 / 3, -45], [2 / 3, 45], [1, 135]])
        self.assertFalse(any("a321/old" in " ".join(l) for l in lines))


runTestCases([TestAnimPresets])
