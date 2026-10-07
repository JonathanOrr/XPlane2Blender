"""
Find and Replace / Duplicate and Replace for the X-Plane text settings of many objects:
the left MCDU's commands become the right MCDU's in one step
"""

import os

import bpy

from io_xplane2blender import xplane_bulk_edit
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

__dirname__ = os.path.dirname(__file__)


def mesh(name: str, material: str = "Material") -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name), material_name=material
    )


def key(name: str, command: str) -> bpy.types.Object:
    obj = mesh(name)
    obj.xplane.manip.enabled = True
    obj.xplane.manip.type = "command"
    obj.xplane.manip.command = command
    obj.xplane.manip.tooltip = "Captain MCDU key"
    return obj


def select(*objects) -> None:
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


class TestBulkEdit(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        self.s = bpy.context.window_manager.xplane_bulk_edit
        self.s.pairs.clear()
        self.s.scope = "SELECTED"
        self.s.kinds = set(xplane_bulk_edit.ALL_KINDS)
        self.s.use_regex = False
        self.s.match_case = True

    def pair(self, find: str, replace: str) -> None:
        p = self.s.pairs.add()
        p.find, p.replace = find, replace

    def test_replaces_every_kind_of_setting_on_the_selection_only(self) -> None:
        a = key("key_A", "a321/mcdu/key/A")
        a.xplane.lightLevel = True
        a.xplane.lightLevel_dataref = "a321/brightness/mcdu_1_keys"
        dataref = a.xplane.datarefs.add()
        dataref.path = "a321/mcdu/key/A_anim"
        other = key("key_B", "a321/mcdu/key/B")
        self.pair("mcdu/", "mcdu_2/")
        self.pair("mcdu_1_", "mcdu_2_")
        self.pair("Captain", "First Officer")
        select(a)

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.bulk_replace())

        self.assertEqual("a321/mcdu_2/key/A", a.xplane.manip.command)
        self.assertEqual("a321/mcdu_2/key/A_anim", a.xplane.datarefs[0].path)
        self.assertEqual("a321/brightness/mcdu_2_keys", a.xplane.lightLevel_dataref)
        self.assertEqual("First Officer MCDU key", a.xplane.manip.tooltip)
        self.assertEqual("a321/mcdu/key/B", other.xplane.manip.command)

    def test_only_the_chosen_kinds_change(self) -> None:
        a = key("key_A", "a321/capt/key")
        a.xplane.manip.tooltip = "capt key"
        self.pair("capt", "fo")
        self.s.kinds = {"COMMANDS"}
        select(a)

        bpy.ops.xplane.bulk_replace()

        self.assertEqual("a321/fo/key", a.xplane.manip.command)
        self.assertEqual("capt key", a.xplane.manip.tooltip)

    def test_match_case_and_regular_expressions(self) -> None:
        a = key("key_A", "a321/Capt/nd_brightness")
        self.pair("capt", "fo")
        select(a)
        bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/Capt/nd_brightness", a.xplane.manip.command)

        self.s.match_case = False
        bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/fo/nd_brightness", a.xplane.manip.command)

        self.s.pairs.clear()
        self.pair(r"(\w+)_brightness$", r"\1_dim")
        self.s.use_regex = True
        bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/fo/nd_dim", a.xplane.manip.command)

    def test_plain_text_replacement_keeps_backslashes(self) -> None:
        a = key("key_A", "a321/key")
        self.pair("key", r"key\1")
        select(a)
        bpy.ops.xplane.bulk_replace()
        self.assertEqual(r"a321/key\1", a.xplane.manip.command)

    def test_a_bad_regular_expression_changes_nothing(self) -> None:
        a = key("key_A", "a321/key")
        self.pair("(", "x")
        self.s.use_regex = True
        select(a)
        # Called from Python, Blender raises the operator's error report
        with self.assertRaises(RuntimeError):
            bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/key", a.xplane.manip.command)

    def test_a_material_shared_with_unselected_objects_is_left_alone(self) -> None:
        left = mesh("left_panel", "Panel")
        right = mesh("right_panel", "Panel")
        mat = left.material_slots[0].material
        self.assertIs(mat, right.material_slots[0].material)
        mat.xplane.lightLevel = True
        mat.xplane.lightLevel_dataref = "a321/capt/panel"
        self.pair("capt", "fo")

        select(left)
        changes, skipped = xplane_bulk_edit.plan([left], [("capt", "fo")])
        self.assertEqual([], changes)
        self.assertEqual([mat], skipped)
        bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/capt/panel", mat.xplane.lightLevel_dataref)

        select(left, right)
        bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/fo/panel", mat.xplane.lightLevel_dataref)

    def test_children_are_included_when_asked(self) -> None:
        parent = key("knob_base", "a321/capt/knob")
        child = key("knob_cap", "a321/capt/knob_push")
        child.parent = parent
        self.pair("capt", "fo")
        self.s.scope = "SELECTED_CHILDREN"
        select(parent)

        bpy.ops.xplane.bulk_replace()

        self.assertEqual("a321/fo/knob_push", child.xplane.manip.command)

    def test_duplicate_and_replace_leaves_the_originals_alone(self) -> None:
        a = key("MCDU_L_key_A", "a321/mcdu/key/A")
        b = key("MCDU_L_key_B", "a321/mcdu/key/B")
        self.pair("mcdu/", "mcdu_2/")
        select(a, b)

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.bulk_duplicate_replace())

        copies = sorted(bpy.context.selected_objects, key=lambda o: o.name)
        self.assertEqual(2, len(copies))
        self.assertNotIn(a, copies)
        self.assertEqual(
            ["a321/mcdu_2/key/A", "a321/mcdu_2/key/B"],
            [c.xplane.manip.command for c in copies],
        )
        self.assertEqual("a321/mcdu/key/A", a.xplane.manip.command)
        self.assertEqual("a321/mcdu/key/B", b.xplane.manip.command)

    def test_nothing_to_find_changes_nothing(self) -> None:
        a = key("key_A", "a321/key")
        self.pair("", "x")
        select(a)
        bpy.ops.xplane.bulk_replace()
        self.assertEqual("a321/key", a.xplane.manip.command)


runTestCases([TestBulkEdit])
