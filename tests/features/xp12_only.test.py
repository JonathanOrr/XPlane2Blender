"""
X-Plane 12 only: files made for older X-Plane versions or for scenery are converted when they are opened
or imported, so they are one click away from an X-Plane 12 export
"""

import os

import bpy

from io_xplane2blender import xplane_constants, xplane_helpers, xplane_updater, xplane_xp12
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.importer_helpers import TempFolder, obj_text, write_file
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file


class TestXP12Only(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()

    def make_old_file(self):
        bpy.context.scene.xplane.version = xplane_constants.VERSION_1100
        for name, export_type in (
            ("hangar", xplane_constants.EXPORT_TYPE_SCENERY),
            ("tree", xplane_constants.EXPORT_TYPE_INSTANCED_SCENERY),
            ("cockpit", xplane_constants.EXPORT_TYPE_COCKPIT),
        ):
            test_creation_helpers.create_datablock_collection(name)
            bpy.data.collections[name].xplane.layer.export_type = export_type
        light = bpy.data.lights.new("old strobe", "POINT")
        light.xplane.type = xplane_constants.LIGHT_STROBE

    def test_old_versions_and_scenery_become_x_plane_12_aircraft(self) -> None:
        self.make_old_file()

        changes = xplane_xp12.convert_to_xp12()

        self.assertEqual(xplane_constants.VERSION_1220, bpy.context.scene.xplane.version)
        types = {c.name: c.xplane.layer.export_type for c in bpy.data.collections}
        self.assertEqual(
            {"hangar": "aircraft", "tree": "aircraft", "cockpit": "cockpit"}, types
        )
        # Old X-Plane 9 lights have no faithful X-Plane 12 version: pointed out, left alone
        self.assertEqual(xplane_constants.LIGHT_STROBE, bpy.data.lights["old strobe"].xplane.type)
        self.assertTrue(any("old strobe" in change for change in changes), changes)
        self.assertEqual(4, len(changes), changes)

    def test_converting_twice_changes_nothing_more(self) -> None:
        self.make_old_file()
        xplane_xp12.convert_to_xp12()
        changes = [c for c in xplane_xp12.convert_to_xp12() if "light" not in c]
        self.assertEqual([], changes)

    def test_files_from_older_add_on_versions_are_converted_when_opened(self) -> None:
        self.make_old_file()
        kept = os.environ.pop(xplane_xp12.KEEP_OLD_SETTINGS_VARIABLE, None)
        try:
            xplane_updater.update(
                xplane_helpers.VerStruct.parse_version("4.5.0-alpha.1+122.20261007140235"),
                xplane_helpers.logger,
            )
        finally:
            if kept is not None:
                os.environ[xplane_xp12.KEEP_OLD_SETTINGS_VARIABLE] = kept
        self.assertEqual(xplane_constants.VERSION_1220, bpy.context.scene.xplane.version)
        self.assertEqual("aircraft", bpy.data.collections["hangar"].xplane.layer.export_type)

    def test_imports_are_set_up_for_x_plane_12(self) -> None:
        bpy.context.scene.xplane.version = xplane_constants.VERSION_1100
        folder = TempFolder()
        try:
            path = write_file(folder.join("xp10_part.obj"), obj_text("", version=800))
            built = import_obj_file(path, ImportOptions(), ImportReport())
        finally:
            folder.cleanup()
        self.assertIsNotNone(built)
        self.assertEqual(xplane_constants.VERSION_1220, bpy.context.scene.xplane.version)
        self.assertIn(built.collection.xplane.layer.export_type, xplane_xp12.FILE_TYPES)


runTestCases([TestXP12Only])
