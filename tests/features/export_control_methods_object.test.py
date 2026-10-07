import inspect

from typing import Tuple
import os
import sys

import bpy
from io_xplane2blender import xplane_config, xplane_constants
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

__dirname__ = os.path.dirname(__file__)

class TestExportControlMethodsObject(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        # The .blend's X-Plane 9 lights are no longer exported. Opening it left them with no light chosen
        for light in bpy.data.lights:
            if light.xplane.type == xplane_constants.LIGHT_AUTOMATIC and not light.xplane.name:
                light.xplane.type = xplane_constants.LIGHT_CUSTOM
    def test_DisabledInViewport(self)->None:
        filename = inspect.stack()[0].function

        self.assertExportableRootExportEqualsFixture(
            filename[5:],
            os.path.join(__dirname__, "fixtures", filename + ".obj"),
            {"ANIM", "DONT_EXPORT_THIS", "LIGHT", "TRIS"},
            filename,
        )

    def test_HiddenInViewport(self)->None:
        filename = inspect.stack()[0].function

        self.assertExportableRootExportEqualsFixture(
            filename[5:],
            os.path.join(__dirname__, "fixtures", filename + ".obj"),
            {"ANIM", "DONT_EXPORT_THIS", "LIGHT", "TRIS"},
            filename,
        )


#TI Same class name above, we only support one TestCase in runTestCases
runTestCases([TestExportControlMethodsObject])
