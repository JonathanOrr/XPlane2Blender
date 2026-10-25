"""
Writing the OBJ file: in UTF-8 whatever the system's code page (Windows' cp1252 cannot write every tooltip), and a
write that fails leaves the OBJ from before, never an empty one
"""

from pathlib import Path
from unittest import mock

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_export
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.xplane_helpers import logger

BEFORE = "I\n800\nOBJ\n"


class TestWriteObjFile(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        self.tmp = Path(get_tmp_folder()) / "write_obj_file"
        self.tmp.mkdir(parents=True, exist_ok=True)
        for old in self.tmp.glob("*.obj*"):
            old.unlink()

    def panel(self, tooltip: str = "APU master") -> None:
        collection = test_creation_helpers.create_datablock_collection("Panel")
        collection.xplane.layer.export_type = C.EXPORT_TYPE_COCKPIT
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "apu", collection="Panel")
        )
        obj.xplane.manip.enabled = True
        obj.xplane.manip.type = "command"
        obj.xplane.manip.command = "a321/apu/master"
        obj.xplane.manip.tooltip = tooltip
        test_creation_helpers.make_root_exportable("Panel").xplane.layer.name = "panel"
        bpy.ops.wm.save_as_mainfile(filepath=str(self.tmp / "write_obj_file.blend"))

    def export(self):
        return bpy.ops.export.xplane_obj(filepath=".", export_is_relative=True)

    def test_a_failed_write_keeps_the_obj_from_before(self) -> None:
        path = self.tmp / "panel.obj"
        path.write_text(BEFORE)

        with self.assertRaises(UnicodeEncodeError):
            xplane_export._write_obj(str(path), BEFORE + "\ud800")  # A lone surrogate has no encoding

        self.assertEqual(BEFORE, path.read_text())
        self.assertEqual([], list(self.tmp.glob("*.part")))

    def test_a_tooltip_a_code_page_lacks_is_written_in_utf8(self) -> None:
        self.panel("APU 主开关 →")

        self.assertEqual({"FINISHED"}, self.export())

        self.assertIn("APU 主开关 →", (self.tmp / "panel.obj").read_bytes().decode("utf-8"))

    def test_a_file_that_cannot_be_written_is_reported_and_kept(self) -> None:
        self.panel()
        (self.tmp / "panel.obj").write_text(BEFORE)

        with mock.patch.object(xplane_export, "_write_obj", side_effect=PermissionError("Access is denied")):
            result = self.export()

        self.assertEqual({"CANCELLED"}, result)
        self.assertEqual(BEFORE, (self.tmp / "panel.obj").read_text())
        self.assertIn("Access is denied", logger.findErrors()[0]["message"])
        logger.clearMessages()


runTestCases([TestWriteObjFile])
