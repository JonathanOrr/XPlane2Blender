import inspect
import os
import sys
from typing import Tuple
from pathlib import Path

import bpy

from io_xplane2blender import xplane_config
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

__dirname__ = os.path.dirname(__file__)


class TestLightLevelPhotometric(XPlaneTestCase):
    def test_feature_exports(self) -> None:
        bpy.context.window.scene = bpy.data.scenes["Scene_v1200"]

        files = [
            "test_exports_photometric_correctly",
            "test_exports_mixed_ll_correctly",
        ]
        for filepath in [
            Path(__dirname__, "fixtures", f"{filename}.obj") for filename in files
        ]:
            with self.subTest(filepath=filepath):
                self.assertExportableRootExportEqualsFixture(
                    filepath.stem[5:],
                    filepath,
                    {"ATTR_light_level"},
                    filepath.name,
                )

runTestCases([TestLightLevelPhotometric])
