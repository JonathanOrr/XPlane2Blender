"""
X-Plane 12 aircraft only: what older files chose for older X-Plane versions or for scenery is converted
when they are opened. Those settings no longer exist, so the old files' stored numbers are written here
as raw values, the way Blender keeps them.
"""

import bpy

from io_xplane2blender import xplane_constants, xplane_helpers, xplane_updater, xplane_xp12
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

# The stored numbers the old drop downs used
OLD_VERSION_1100 = 5
OLD_SCENERY, OLD_INSTANCED_SCENERY = 2, 3
OLD_STROBE_LIGHT = 3


class TestXP12Only(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()

    def make_old_file(self):
        bpy.context.scene.xplane["version"] = OLD_VERSION_1100
        for name, export_type in (
            ("hangar", OLD_SCENERY),
            ("tree", OLD_INSTANCED_SCENERY),
            ("cockpit", 1),
        ):
            test_creation_helpers.create_datablock_collection(name)
            bpy.data.collections[name].xplane.layer["export_type"] = export_type
        light = bpy.data.lights.new("old strobe", "POINT")
        light.xplane["type"] = OLD_STROBE_LIGHT
        light.xplane.name = "kept from before"
        material = bpy.data.materials.new("taxiway paint")
        material.xplane["draped"] = True

    def test_old_versions_and_scenery_become_x_plane_12_aircraft(self) -> None:
        self.make_old_file()

        changes = xplane_xp12.convert_to_xp12()

        self.assertNotIn("version", bpy.context.scene.xplane)
        types = {c.name: c.xplane.layer.export_type for c in bpy.data.collections}
        self.assertEqual({"hangar": "aircraft", "tree": "aircraft", "cockpit": "cockpit"}, types)
        # X-Plane 9 lights have no X-Plane 12 version: they wait for a light to be picked
        light = bpy.data.lights["old strobe"].xplane
        self.assertEqual((xplane_constants.LIGHT_AUTOMATIC, ""), (light.type, light.name))
        self.assertNotIn("draped", bpy.data.materials["taxiway paint"].xplane)
        self.assertEqual(4, len(changes), changes)
        self.assertTrue(any("old strobe" in change for change in changes), changes)

    def test_converting_twice_changes_nothing_more(self) -> None:
        self.make_old_file()
        xplane_xp12.convert_to_xp12()
        self.assertEqual([], xplane_xp12.convert_to_xp12())

    def test_current_lights_are_left_alone(self) -> None:
        light = bpy.data.lights.new("beacon", "POINT")
        light.xplane.type = xplane_constants.LIGHT_NAMED
        light.xplane.name = "airplane_beacon"
        self.assertEqual([], xplane_xp12.convert_to_xp12())
        self.assertEqual((xplane_constants.LIGHT_NAMED, "airplane_beacon"), (light.xplane.type, light.xplane.name))

    def test_files_from_older_add_on_versions_are_converted_when_opened(self) -> None:
        self.make_old_file()
        xplane_updater.update(
            xplane_helpers.VerStruct.parse_version("4.5.0-alpha.1+122.20261007140235"), xplane_helpers.logger
        )
        self.assertNotIn("version", bpy.context.scene.xplane)
        self.assertEqual("aircraft", bpy.data.collections["hangar"].xplane.layer.export_type)


runTestCases([TestXP12Only])
