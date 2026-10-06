import os

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests.test_creation_helpers import *
from io_xplane2blender.xplane_constants import EXPORT_TYPE_AIRCRAFT, EXPORT_TYPE_COCKPIT

__dirname__ = os.path.dirname(__file__)


class TestCameraCollisionAircraft(XPlaneTestCase):
    def _setup(self, export_type, solid_camera):
        create_initial_test_setup()
        coll = create_datablock_collection("Layer 1")
        coll.xplane.layer.export_type = export_type
        mesh = create_datablock_mesh(
            DatablockInfo("MESH", "Cube", collection="Layer 1")
        )
        mesh.material_slots[0].material.xplane.solid_camera = solid_camera

    def test_aircraft_solid_camera_errors(self):
        self._setup(EXPORT_TYPE_AIRCRAFT, True)
        self.exportLayer(0)
        self.assertLoggerErrors(1)

    def test_aircraft_without_solid_camera_no_errors(self):
        self._setup(EXPORT_TYPE_AIRCRAFT, False)
        self.exportLayer(0)
        self.assertLoggerErrors(0)

    def test_cockpit_solid_camera_no_errors(self):
        self._setup(EXPORT_TYPE_COCKPIT, True)
        self.exportLayer(0)
        self.assertLoggerErrors(0)


runTestCases([TestCameraCollisionAircraft])
