"""
The Table panel's list: what it lists and in what order, that the work is not repeated on every redraw (a production
aircraft has thousands of objects), and that every kind of row draws at every width
"""

from types import SimpleNamespace

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_table
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout
from io_xplane2blender.xplane_table import view

BIT = 1 << 30


def mesh(name: str) -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(test_creation_helpers.DatablockInfo("MESH", name))


def key(name: str, command: str) -> bpy.types.Object:
    obj = mesh(name)
    obj.xplane.manip.enabled = True
    obj.xplane.manip.type = "command"
    obj.xplane.manip.command = command
    return obj


def light(name: str, kind: str = C.LIGHT_PARAM, lights_txt_name: str = "airplane_landing_pm") -> bpy.types.Object:
    obj = test_creation_helpers.create_datablock_light(test_creation_helpers.DatablockInfo("LIGHT", name), "SPOT")
    obj.data.xplane.type = kind
    obj.data.xplane.name = lights_txt_name
    return obj


def listed(text: str = "", invert: bool = False):
    """The names of the listed objects in the order they are listed, as the panel's list asks for them"""
    objects = bpy.context.scene.objects
    flags, order = view.filter_and_order(bpy.context, objects, text, invert, BIT)
    shown = [(order[i], o.name) for i, o in enumerate(objects) if flags[i]]
    return [name for _, name in sorted(shown)]


class TestTableView(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        view.table_settings(bpy.context).selected_only = False
        view.table_settings(bpy.context).table = "MANIPULATORS"
        view.scene_changed()

    def test_lists_what_the_table_is_about_sorted_by_name(self) -> None:
        key("key_b", "a321/key/B")
        key("Key_A", "a321/key/A")
        key("key_c", "a321/key/C")
        mesh("not_clickable")
        self.assertEqual(["Key_A", "key_b", "key_c"], listed())
        self.assertEqual(3, xplane_table.table_count(bpy.context))

    def test_the_search_looks_in_names_and_commands(self) -> None:
        key("key_A", "a321/mcdu/key/A")
        key("key_B", "a321/fcu/key/B")
        self.assertEqual(["key_A"], listed("mcdu"))
        self.assertEqual(["key_B"], listed("KEY_B"))
        self.assertEqual(["key_A", "key_B"], listed("key"))

    def test_inverting_the_search_lists_the_rest(self) -> None:
        key("key_A", "a321/mcdu/key/A")
        key("key_B", "a321/fcu/key/B")
        self.assertEqual(["key_B"], listed("mcdu", invert=True))
        # Nothing to search for: inverting changes nothing
        self.assertEqual(["key_A", "key_B"], listed("", invert=True))

    def test_selected_only(self) -> None:
        a = key("key_A", "a")
        key("key_B", "b")
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        a.select_set(True)
        view.table_settings(bpy.context).selected_only = True
        self.assertEqual(["key_A"], listed())

    def test_every_table_lists_its_own_objects(self) -> None:
        key("key_A", "a")
        glow = mesh("glow")
        glow.xplane.lightLevel = True
        moving = mesh("moving")
        moving.xplane.datarefs.add().path = "a321/move"
        light("lamp")
        settings = view.table_settings(bpy.context)
        for table, expected in (
            ("MANIPULATORS", ["key_A"]),
            ("LIGHT_LEVELS", ["glow"]),
            ("ANIMATIONS", ["moving"]),
            ("LIGHTS", ["lamp"]),
        ):
            with self.subTest(table=table):
                settings.table = table
                self.assertEqual(expected, listed())

    def test_the_search_finds_lights_by_their_lights_txt_name_and_parameters(self) -> None:
        light("lamp_landing", lights_txt_name="airplane_landing_pm").data.xplane.params = "1 1 1 0 20000cd 0 0 -1 0.9"
        light("lamp_beacon", lights_txt_name="airplane_beacon_bb")
        view.table_settings(bpy.context).table = "LIGHTS"
        self.assertEqual(["lamp_landing"], listed("landing_pm"))
        self.assertEqual(["lamp_landing"], listed("20000cd"))

    def test_the_order_puts_every_object_in_its_own_place(self) -> None:
        for name in "dbca":
            key(name, "x")
        mesh("other")
        _, order = view.filter_and_order(bpy.context, bpy.context.scene.objects, "", False, BIT)
        self.assertEqual(list(range(len(order))), sorted(order))

    def test_what_was_found_is_kept_until_the_scene_changes(self) -> None:
        key("key_A", "a")
        first = view.filter_and_order(bpy.context, bpy.context.scene.objects, "", False, BIT)
        self.assertIs(first, view.filter_and_order(bpy.context, bpy.context.scene.objects, "", False, BIT))
        key("key_B", "b")  # A new object changes how many there are
        self.assertEqual(["key_A", "key_B"], listed())
        # Turning a setting on does not change the count, the scene's change handler says so
        later = mesh("later")
        self.assertEqual(["key_A", "key_B"], listed())
        later.xplane.manip.enabled = True
        view.scene_changed()
        self.assertEqual(["key_A", "key_B", "later"], listed())

    def test_clicking_a_row_selects_the_object(self) -> None:
        key("key_A", "a")
        wanted = key("key_B", "b")
        position = list(bpy.context.scene.objects).index(wanted)
        view.table_settings(bpy.context).index = position
        self.assertTrue(wanted.select_get())
        self.assertIs(wanted, bpy.context.view_layer.objects.active)

    def test_the_list_marks_the_row_of_the_active_object(self) -> None:
        first = key("key_A", "a")
        second = key("key_B", "b")
        loose = mesh("not in the table")
        settings = view.table_settings(bpy.context)
        for obj in (first, second):
            bpy.context.view_layer.objects.active = obj
            view.scene_changed()
            self.assertEqual(list(bpy.context.scene.objects).index(obj), settings.index)
        bpy.context.view_layer.objects.active = loose
        self.assertEqual(-1, settings.index)

    def test_every_kind_of_row_draws_at_every_width(self) -> None:
        key("key_A", "a")
        glow = mesh("glow")
        glow.xplane.lightLevel = True
        moving = mesh("moving")
        moving.xplane.datarefs.add().path = "a321/move"
        moving.xplane.datarefs.add().path = "a321/move2"
        objects = {"MANIPULATORS": bpy.data.objects["key_A"], "LIGHT_LEVELS": glow, "ANIMATIONS": moving}
        for kind in (C.LIGHT_NAMED, C.LIGHT_PARAM, C.LIGHT_AUTOMATIC, C.LIGHT_CUSTOM, C.LIGHT_SPILL_CUSTOM, C.LIGHT_NON_EXPORTING):
            objects[f"LIGHTS {kind}"] = light(f"lamp {kind}", kind)
        settings = view.table_settings(bpy.context)
        for label, obj in objects.items():
            for width in (200, 500, 900):
                with self.subTest(table=label, width=width):
                    settings.table = label.split()[0]
                    context = SimpleNamespace(
                        window_manager=bpy.context.window_manager,
                        region=SimpleNamespace(width=width),
                        preferences=bpy.context.preferences,
                    )
                    layout = FakeLayout()
                    view.XPLANE_UL_object_table.draw_item(None, context, layout, None, obj, 0, None, "", 0)
                    self.assertIn(obj.name, layout.labels())


runTestCases([TestTableView])
