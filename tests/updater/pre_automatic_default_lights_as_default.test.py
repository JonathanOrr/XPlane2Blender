import inspect

from typing import Tuple
import os
import sys

import bpy
from io_xplane2blender import xplane_constants, xplane_config
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers


class TestPreAutomaticDefaultLightsAsDefault(XPlaneTestCase):
    def test_old_default_lights_wait_for_a_light_to_be_picked(self)->None:
        # Before automatic lights, a light with no type was an X-Plane 9 "default" light,
        # which X-Plane 12 has no equivalent for: it is left with no light chosen
        for light in bpy.data.lights:
            self.assertEqual(light.xplane.type, xplane_constants.LIGHT_AUTOMATIC)
            self.assertEqual(light.xplane.name, "")


runTestCases([TestPreAutomaticDefaultLightsAsDefault])
