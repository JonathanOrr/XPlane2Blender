import bpy
import os
from io_xplane2blender import xplane_constants
from io_xplane2blender.tests import *
from io_xplane2blender.xplane_config import getDebug
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types import xplane_file

__dirname__ = os.path.dirname(__file__)

class TestTEXTURE_MAP_export(XPlaneTestCase):
    def test_export(self):
        def filterLines(line):
            return isinstance(line[0],str) and (\
                'TEXTURE' in line[0] or\
                'NORMAL' in line[0]\
                )

        filename = 'test_TEXTURE_MAP'

        for test_case in [ 'TEXTURE_MAP_normal_material_gloss', 'TEXTURE_MAP_normal', 'TEXTURE_MAP_normal_gloss' ]:
            self.assertExportableRootExportEqualsFixture(
                test_case,
                os.path.join(__dirname__, "../fixtures", f"{test_case}.obj"),
                filterLines,
                filename,
        )

    def test_only_the_chosen_textures_are_written(self):
        # Made before the choice existed with both kinds of normal texture, which used to stop the export
        root = bpy.data.collections.get("TEXTURE_MAP_normal_error") or bpy.data.objects["TEXTURE_MAP_normal_error"]
        layer = root.xplane.layer
        self.assertTrue(layer.texture_normal and layer.texture_map_normal)
        self.assertEqual(layer.normal_maps, xplane_constants.NORMAL_MAPS_ONE)
        out = self.exportExportableRoot(root)
        self.assertLoggerErrors(0)
        self.assertIn("TEXTURE_NORMAL", out)
        self.assertNotIn("TEXTURE_MAP", out)

        layer.normal_maps = xplane_constants.NORMAL_MAPS_GLOSS
        out = self.exportExportableRoot(root)
        self.assertLoggerErrors(0)
        self.assertIn("TEXTURE_MAP normal", out)
        self.assertNotIn("TEXTURE_NORMAL", out)
        # Switching back keeps what was typed in
        self.assertTrue(layer.texture_normal)


runTestCases([TestTEXTURE_MAP_export])
