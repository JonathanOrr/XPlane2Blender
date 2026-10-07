"""
Imports aircraft that ship with X-Plane. They can't be part of this repository, so these tests only run when
the XP2B_TEST_XPLANE environment variable points at an X-Plane 11 or 12 folder, for example
    XP2B_TEST_XPLANE="/home/me/X-Plane 12" python3 tests.py -f import_real
"""
import glob
import os

import bpy
import mathutils

from io_xplane2blender.tests import *
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.aircraft import import_aircraft
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport

XPLANE = os.environ.get("XP2B_TEST_XPLANE", "")


def find_acf(*patterns: str) -> str:
    for pattern in patterns:
        found = glob.glob(os.path.join(XPLANE, "Aircraft", "**", pattern), recursive=True)
        if found:
            return sorted(found)[0]
    return ""


def world_size(collection):
    points = [
        o.matrix_world @ mathutils.Vector(corner)
        for o in collection.all_objects
        if o.type == "MESH" and not o.hide_render
        for corner in o.bound_box
    ]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    return [h - l for h, l in zip(high, low)]


class TestImportRealAircraft(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        if not XPLANE or not os.path.isdir(XPLANE):
            self.skipTest("Set XP2B_TEST_XPLANE to an X-Plane folder to run this")
        create_initial_test_setup()

    def import_acf(self, path: str):
        report = ImportReport()
        root = import_aircraft(path, ImportOptions(), report)
        self.assertIsNotNone(root, report.errors)
        self.assertEqual(report.files_failed, 0, report.errors)
        return root, report

    def test_cessna_172(self) -> None:
        path = find_acf("Cessna_172SP.acf")
        if not path:
            self.skipTest("There is no Cessna 172 in this X-Plane")
        root, report = self.import_acf(path)
        span, length, height = world_size(root)
        self.assertAlmostEqual(span, 10.98, delta=0.3)
        self.assertAlmostEqual(length, 8.27, delta=0.3)
        self.assertAlmostEqual(height, 2.8, delta=0.4)
        self.assertGreater(report.meshes_imported, 300)
        self.assertGreater(report.manipulators_imported, 50)
        self.assertGreater(report.animations_imported, 100)

    def test_an_airliner(self) -> None:
        path = find_acf("b738.acf")
        if not path:
            self.skipTest("There is no 737 in this X-Plane")
        root, report = self.import_acf(path)
        span, length, _ = world_size(root)
        self.assertAlmostEqual(span, 35.8, delta=1.5)
        self.assertAlmostEqual(length, 39.5, delta=1.5)

    def test_every_aircraft_imports(self) -> None:
        paths = [p for p in glob.glob(os.path.join(XPLANE, "Aircraft", "*", "*", "*.acf"))]
        if not paths:
            self.skipTest("No aircraft found")
        for path in sorted(paths)[:8]:
            with self.subTest(aircraft=os.path.basename(path)):
                create_initial_test_setup()
                report = ImportReport()
                root = import_aircraft(path, ImportOptions(), report)
                self.assertIsNotNone(root, report.errors)
                self.assertEqual(report.files_failed, 0, report.errors)


runTestCases([TestImportRealAircraft])
