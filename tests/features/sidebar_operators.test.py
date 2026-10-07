"""
The X-Plane sidebar's operators do what their buttons say
"""

from types import SimpleNamespace

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender import xplane_sidebar as S
from io_xplane2blender import xplane_helpers, xplane_ui
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout, draw_panel

PANELS = [
    cls
    for cls in S._classes
    if isinstance(cls, type) and issubclass(cls, bpy.types.Panel)
]
MENUS = [cls for cls in S._classes if isinstance(cls, type) and issubclass(cls, bpy.types.Menu)]


def mesh(name: str, collection: str = "Panel") -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name, collection=collection)
    )


def make_active(*objects) -> None:
    for obj in bpy.context.view_layer.objects:
        if obj is not None:
            obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


class TestSidebarOperators(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        test_creation_helpers.create_datablock_collection("Panel")

    def test_making_switches_sets_kind_and_cursor_on_all_selected(self) -> None:
        a, b = mesh("a"), mesh("b")
        b.xplane.manip.enabled = True
        b.xplane.manip.type = C.MANIP_COMMAND
        b.xplane.manip.cursor = C.MANIP_CURSOR_FOUR_ARROWS  # chosen by hand, stays
        make_active(a, b)
        bpy.ops.xplane.set_control_kind(kind=C.MANIP_COMMAND_SWITCH_UP_DOWN2)
        for obj in (a, b):
            self.assertTrue(obj.xplane.manip.enabled)
            self.assertEqual(C.MANIP_COMMAND_SWITCH_UP_DOWN2, obj.xplane.manip.type)
        self.assertEqual(C.MANIP_CURSOR_UP_DOWN, a.xplane.manip.cursor)
        self.assertEqual(C.MANIP_CURSOR_FOUR_ARROWS, b.xplane.manip.cursor)

    def test_key_pose_keys_value_and_transform_linearly(self) -> None:
        obj = mesh("lever")
        make_active(obj)
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM)
        obj.xplane.datarefs[0].path = "a321/lever"
        for frame, value, angle in ((1, 0.0, 0.0), (10, 1.0, 0.5)):
            bpy.context.scene.frame_set(frame)
            obj.xplane.datarefs[0].value = value
            obj.rotation_euler[0] = angle
            bpy.ops.xplane.key_pose(index=0)
        self.assertEqual([(1.0, 0.0), (10.0, 1.0)], I.dataref_keys(obj, 0))
        fcurves = {f.data_path for f in xplane_helpers.get_action_fcurves(obj)}
        self.assertIn("rotation_euler", fcurves)
        for fcurve in xplane_helpers.get_action_fcurves(obj):
            self.assertTrue(all(k.interpolation == "LINEAR" for k in fcurve.keyframe_points))

    def test_removing_a_dataref_keeps_the_keys_of_the_others(self) -> None:
        obj = mesh("lever")
        make_active(obj)
        for path in ("first", "second"):
            bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM)
            obj.xplane.datarefs[-1].path = path
            for frame, value in ((1, 0.0), (10, 5.0)):
                bpy.context.scene.frame_set(frame)
                obj.xplane.datarefs[-1].value = value
                bpy.ops.xplane.key_pose(index=len(obj.xplane.datarefs) - 1)
        bpy.ops.xplane.remove_dataref(index=0)
        self.assertEqual(["second"], [d.path for d in obj.xplane.datarefs])
        self.assertEqual([(1.0, 0.0), (10.0, 5.0)], I.dataref_keys(obj, 0))

    def test_search_fills_the_target_and_keeps_cmnd(self) -> None:
        obj = mesh("button")
        make_active(obj)
        S._search_values[:] = ["sim/lights/landing_lights_on"]
        S._search_items[:] = [("0", "sim/lights/landing_lights_on", "")]
        bpy.ops.xplane.search(kind="command", target="object:xplane.manip.command", choice="0")
        self.assertEqual("sim/lights/landing_lights_on", obj.xplane.manip.command)
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM)
        obj.xplane.datarefs[0].path = "CMND=old"
        bpy.ops.xplane.search(kind="command", target="object:xplane.datarefs[0].path", choice="0")
        self.assertEqual("CMND=sim/lights/landing_lights_on", obj.xplane.datarefs[0].path)

    def test_names_in_file_include_custom_ones(self) -> None:
        obj = mesh("button")
        obj.xplane.manip.enabled = True
        obj.xplane.manip.command = "a321/mcdu/1/key_a"
        obj.xplane.lightLevel_dataref = "a321/lights/integ"
        self.assertEqual(["a321/mcdu/1/key_a"], S.names_in_file("command"))
        self.assertEqual(["a321/lights/integ"], S.names_in_file("dataref"))
        self.assertGreater(len(S._xplane_list("command")), 1000)
        self.assertGreater(len(S._xplane_list("dataref")), 1000)

    def test_add_menu_items(self) -> None:
        bpy.ops.xplane.add_click_zone()
        zone = bpy.context.active_object
        self.assertTrue(zone.xplane.manip.enabled)
        self.assertFalse(zone.active_material.xplane.draw)
        bpy.ops.xplane.add_light(kind=C.LIGHT_SPILL_CUSTOM)
        self.assertEqual(C.LIGHT_SPILL_CUSTOM, bpy.context.active_object.data.xplane.type)
        bpy.ops.xplane.add_attachment(kind=C.EMPTY_USAGE_WHEEL)
        self.assertEqual(C.EMPTY_USAGE_WHEEL, bpy.context.active_object.xplane.special_empty_props.special_type)


runTestCases([TestSidebarOperators])
