"""
The X-Plane tables: manipulators, light levels and animation datarefs of many objects, written to CSV for a
spreadsheet and read back by object name
"""

import csv
import os
from pathlib import Path

import bpy

from io_xplane2blender import xplane_table
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

__dirname__ = os.path.dirname(__file__)


def mesh(name: str) -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(test_creation_helpers.DatablockInfo("MESH", name))


def key(name: str, command: str) -> bpy.types.Object:
    obj = mesh(name)
    obj.xplane.manip.enabled = True
    obj.xplane.manip.type = "command"
    obj.xplane.manip.command = command
    obj.xplane.manip.tooltip = "key"
    return obj


def read(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path: Path, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class TestTableCsv(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        self.tmp = Path(get_tmp_folder()) / "table_csv"
        self.tmp.mkdir(parents=True, exist_ok=True)

    def test_manipulators_round_trip_through_a_spreadsheet(self) -> None:
        a = key("key_A", "a321/mcdu/key/A")
        b = key("key_B", "a321/mcdu/key/B")
        mesh("no_manipulator")
        path = self.tmp / "manipulators.csv"

        count = xplane_table.write_csv(str(path), list(bpy.context.scene.objects), "MANIPULATORS")

        rows = read(path)
        self.assertEqual(2, count)
        self.assertEqual(["key_A", "key_B"], [r["object"] for r in rows])
        self.assertEqual("a321/mcdu/key/A", rows[0]["command"])
        self.assertEqual("true", rows[0]["enabled"])
        rows[0]["command"] = "a321/mcdu/key/A_new"
        rows[1]["tooltip"] = "Key B"
        write(path, rows)

        result = xplane_table.read_csv(str(path), "MANIPULATORS", bpy.context.scene)

        self.assertEqual("a321/mcdu/key/A_new", a.xplane.manip.command)
        self.assertEqual("Key B", b.xplane.manip.tooltip)
        self.assertEqual(2, result.changed)
        self.assertEqual({"key_A", "key_B"}, result.objects)
        self.assertEqual([], result.problems)

    def test_unknown_objects_and_bad_values_are_reported_not_fatal(self) -> None:
        a = key("key_A", "a321/key/A")
        path = self.tmp / "bad.csv"
        xplane_table.write_csv(str(path), [a], "MANIPULATORS")
        rows = read(path)
        rows[0]["type"] = "not_a_type"
        rows[0]["v_down"] = "lots"
        rows[0]["command"] = "a321/key/A2"
        rows.append(dict(rows[0], object="deleted_object"))
        write(path, rows)

        result = xplane_table.read_csv(str(path), "MANIPULATORS", bpy.context.scene)

        self.assertEqual("a321/key/A2", a.xplane.manip.command)
        self.assertEqual("command", a.xplane.manip.type)
        self.assertEqual(["deleted_object"], result.unknown_objects)
        self.assertEqual(2, len(result.problems), result.problems)
        self.assertIn("not found", result.summary())

    def test_light_levels_and_true_false_spellings(self) -> None:
        obj = mesh("button_lit")
        obj.xplane.lightLevel = True
        obj.xplane.lightLevel_dataref = ""
        path = self.tmp / "light_levels.csv"
        xplane_table.write_csv(str(path), [obj], "LIGHT_LEVELS")
        rows = read(path)
        rows[0]["lightLevel_dataref"] = "a321/brightness/ovhd"
        rows[0]["lightLevel_v2"] = "0,8"
        rows[0]["lightLevel_photometric"] = "YES"
        write(path, rows)

        xplane_table.read_csv(str(path), "LIGHT_LEVELS", bpy.context.scene)

        self.assertEqual("a321/brightness/ovhd", obj.xplane.lightLevel_dataref)
        self.assertAlmostEqual(0.8, obj.xplane.lightLevel_v2, places=5)
        self.assertTrue(obj.xplane.lightLevel_photometric)

    def test_animation_datarefs_have_one_row_each(self) -> None:
        obj = mesh("switch")
        for path_text in ("a321/switch/anim", "a321/switch/guard"):
            d = obj.xplane.datarefs.add()
            d.path = path_text
        path = self.tmp / "animations.csv"
        xplane_table.write_csv(str(path), [obj], "ANIMATIONS")
        rows = read(path)
        self.assertEqual(["0", "1"], [r["index"] for r in rows])
        self.assertNotIn("value", rows[0])
        rows[1]["path"] = "a321/switch/guard_open"
        rows.append(dict(rows[1], index="2", path="a321/switch/light", anim_type="show"))
        write(path, rows)

        xplane_table.read_csv(str(path), "ANIMATIONS", bpy.context.scene)

        self.assertEqual(
            ["a321/switch/anim", "a321/switch/guard_open", "a321/switch/light"],
            [d.path for d in obj.xplane.datarefs],
        )
        self.assertEqual("show", obj.xplane.datarefs[2].anim_type)

    def test_an_empty_table_still_has_its_columns(self) -> None:
        path = self.tmp / "empty.csv"
        self.assertEqual(0, xplane_table.write_csv(str(path), [], "MANIPULATORS"))
        with open(path, encoding="utf-8") as f:
            columns = f.readline().strip().split(",")
        self.assertEqual("object", columns[0])
        self.assertIn("command", columns)
        self.assertNotIn("__xplane_table_sample__", bpy.data.objects)

    def test_the_main_setting_follows_the_manipulator_type(self) -> None:
        m = key("knob", "x").xplane.manip
        m.type = "command_knob"
        self.assertEqual("positive_command", xplane_table.main_manip_setting(m))
        m.type = "command_knob2"
        self.assertEqual("command", xplane_table.main_manip_setting(m))
        m.type = "drag_axis"
        self.assertEqual("dataref1", xplane_table.main_manip_setting(m))


runTestCases([TestTableCsv])
