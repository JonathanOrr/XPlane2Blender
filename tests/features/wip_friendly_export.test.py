"""
Exporting work in progress is normal: settings that are not filled in yet are left out and counted,
and one file with a problem never stops the other files of the export from being written
"""

import os
from pathlib import Path

import bpy

from io_xplane2blender import xplane_helpers
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.xplane_helpers import logger, unfinished

__dirname__ = os.path.dirname(__file__)


def mesh(name: str, collection: str) -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name, collection=collection)
    )


def lines_starting(out: str, directive: str):
    return [line.split() for line in out.splitlines() if line.split()[:1] == [directive]]


class TestWipFriendlyExport(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        unfinished.clear()

    def test_light_level_without_a_dataref_is_left_out(self) -> None:
        test_creation_helpers.create_datablock_collection("Panel")
        obj = mesh("button_lit", "Panel")
        obj.xplane.lightLevel = True
        obj.xplane.lightLevel_dataref = ""
        done = mesh("button_done", "Panel")
        done.xplane.lightLevel = True
        done.xplane.lightLevel_dataref = "a321/panel/brightness"

        out = self.exportExportableRoot("Panel")

        self.assertEqual(
            [["ATTR_light_level", "0", "1", "a321/panel/brightness"]],
            lines_starting(out, "ATTR_light_level"),
        )
        self.assertFalse(logger.hasErrors())
        self.assertEqual(["button_lit"], unfinished.items["light levels without a dataref"])

    def test_light_without_a_name_is_left_out(self) -> None:
        from io_xplane2blender.xplane_utils import xplane_lights_txt_parser

        xplane_lights_txt_parser.parse_lights_file()
        test_creation_helpers.create_datablock_collection("Panel")
        mesh("panel", "Panel")
        for name in ("flood", "dome"):
            data = bpy.data.lights.new(name, "SPOT")
            data.xplane.type = "automatic"
            data.xplane.name = "" if name == "flood" else "airplane_landing_core"
            obj = bpy.data.objects.new(name, data)
            bpy.data.collections["Panel"].objects.link(obj)

        out = self.exportExportableRoot("Panel")

        self.assertFalse(logger.hasErrors(), logger.messagesToString())
        self.assertEqual(1, len(lines_starting(out, "LIGHT_PARAM")))
        self.assertEqual(["flood"], unfinished.items["lights without an X-Plane light chosen"])

    def test_material_light_level_without_a_dataref_is_left_out(self) -> None:
        test_creation_helpers.create_datablock_collection("Panel")
        obj = mesh("panel_lit", "Panel")
        mat = obj.material_slots[0].material
        mat.xplane.lightLevel = True
        mat.xplane.lightLevel_dataref = "   "

        out = self.exportExportableRoot("Panel")

        self.assertEqual([], lines_starting(out, "ATTR_light_level"))
        self.assertFalse(logger.hasErrors())
        self.assertIn("light levels without a dataref", unfinished.items)

    def test_mesh_without_a_material_exports_with_default_settings(self) -> None:
        test_creation_helpers.create_datablock_collection("Panel")
        obj = mesh("new_part", "Panel")
        obj.data.materials.clear()

        out = self.exportExportableRoot("Panel")

        self.assertFalse(logger.hasErrors())
        self.assertEqual(1, len(lines_starting(out, "TRIS")))
        self.assertEqual(
            ["new_part"],
            unfinished.items["meshes without a material (default material used)"],
        )

    def test_a_file_with_errors_does_not_stop_the_others(self) -> None:
        tmp = Path(get_tmp_folder()) / "wip_friendly_export"
        tmp.mkdir(parents=True, exist_ok=True)
        for old in tmp.glob("*.obj"):
            old.unlink()

        # Collection error: an animation dataref that objects must not use
        test_creation_helpers.create_datablock_collection("Bad Collect")
        bad = mesh("bad_anim", "Bad Collect")
        dataref = bad.xplane.datarefs.add()
        dataref.path = "sim/multiplayer/position/plane1_x"
        dataref.anim_type = "show"
        # Write error: a path that is not relative to the .blend file
        test_creation_helpers.create_datablock_collection("Bad Path")
        mesh("bad_path", "Bad Path")
        # A root with nothing in it is skipped, not a failure
        test_creation_helpers.create_datablock_collection("Empty")
        test_creation_helpers.create_datablock_collection("Good")
        mesh("good", "Good")
        for name, file_name in (
            ("Bad Collect", "bad_collect"),
            ("Bad Path", "/absolute/bad_path"),
            ("Empty", "empty"),
            ("Good", "good"),
        ):
            root = test_creation_helpers.make_root_exportable(name)
            root.xplane.layer.name = file_name
        bpy.ops.wm.save_as_mainfile(filepath=str(tmp / "wip_friendly_export.blend"))

        result = bpy.ops.export.xplane_obj(filepath=".", export_is_relative=True)

        self.assertEqual({"FINISHED"}, result)
        self.assertTrue((tmp / "good.obj").is_file())
        self.assertFalse((tmp / "bad_collect.obj").exists())
        self.assertEqual(2, len(logger.findErrors()))
        summary = [m["message"] for m in logger.findInfos() if m["message"].startswith("Exported")]
        self.assertEqual(1, len(summary), logger.messagesToString())
        self.assertIn("Exported 1 file(s)", summary[0])
        self.assertIn("2 not written because of errors", summary[0])
        self.assertIn("bad_collect", summary[0])
        logger.clearMessages()

    def test_only_errors_everywhere_still_cancels(self) -> None:
        tmp = Path(get_tmp_folder()) / "wip_friendly_export_all_bad"
        tmp.mkdir(parents=True, exist_ok=True)
        test_creation_helpers.create_datablock_collection("Bad Path")
        mesh("bad_path", "Bad Path")
        root = test_creation_helpers.make_root_exportable("Bad Path")
        root.xplane.layer.name = "/absolute/bad_path"
        bpy.ops.wm.save_as_mainfile(filepath=str(tmp / "all_bad.blend"))

        result = bpy.ops.export.xplane_obj(filepath=".", export_is_relative=True)

        self.assertEqual({"CANCELLED"}, result)
        self.assertLoggerErrors(1)


runTestCases([TestWipFriendlyExport])
