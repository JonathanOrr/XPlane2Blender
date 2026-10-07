import bpy
import os
import sys
from io_xplane2blender.tests import *
from io_xplane2blender.xplane_config import getDebug
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types import xplane_file

__dirname__ = os.path.dirname(__file__)

class TestNoMaterial(XPlaneTestCase):
    def test_no_material(self):
        # A mesh without a material is work in progress, not an error: it exports with the default material state
        out = self.exportLayer(0)
        self.assertLoggerErrors(0)
        self.assertIn("TRIS", out)

runTestCases([TestNoMaterial])
