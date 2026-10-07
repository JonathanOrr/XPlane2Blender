import inspect
import os
import sys
from pathlib import Path
from typing import Tuple

import bpy

from io_xplane2blender import xplane_config
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers

__dirname__ = os.path.dirname(__file__)


class TestRainHeaderProps(XPlaneTestCase):
    def test_thermal_wiper_fixtures(self) -> None:
        # The .blend is from X-Plane 12.0, which had no defrost times
        rain = bpy.data.collections["thermal_options"].xplane.layer.rain
        for i in range(1, 5):
            getattr(rain, f"thermal_source_{i}").defrost_time = str(i * 10)
        filenames = [
            "test_thermal_options",
            #"test_thermal2_options",
            "test_wiper_options",
        ]
        for filepath in [
            Path(__dirname__, "fixtures", f"{filename}.obj")
            for filename in filenames
        ]:
            with self.subTest(filepath=filepath):
                root_name = filepath.stem.replace("test_", "")
                self.assertExportableRootExportEqualsFixture(
                    root_object=root_name,
                    fixturePath=filepath,
                    filterCallback={"RAIN_scale", "THERMAL", "WIPER"},
                    tmpFilename=filepath.stem,
                )

    def test_no_options(self) -> None:
        filenames = [
            "test_missing_paths_no_options",
            "test_none_enabled_no_options",
        ]
        for filepath in [
            Path(__dirname__, "fixtures", f"{filename}.obj")
            for filename in filenames
        ]:
            with self.subTest(filepath=filepath):
                root_name = filepath.stem.replace("test_", "")
                self.assertExportableRootExportEqualsFixture(
                    root_object=root_name,
                    fixturePath=filepath,
                    filterCallback={"RAIN_scale", "THERMAL", "WIPER"},
                    tmpFilename=filepath.stem,
                )

    def test_errors(self) -> None:
        # Sources 1 and 3 have neither a defrost time nor a dataref, source 2 has no defrost time
        self.exportExportableRoot("thermal_errors",)
        self.assertLoggerErrors(5)
        self.exportExportableRoot("wiper_errors",)
        self.assertLoggerErrors(3)


runTestCases([TestRainHeaderProps])
