import os

import bpy
import io_xplane2blender.tests.test_creation_helpers
from io_xplane2blender.tests.test_creation_helpers import *
from io_xplane2blender.tests import *
from io_xplane2blender.xplane_constants import *

__dirname__ = os.path.dirname(__file__)


def _wheel_lines(out: str):
    return [
        " ".join(line.split())
        for line in out.splitlines()
        if line.split()[:1] == ["ATTR_manip_wheel"]
    ]


class TestDragRotateWheel(XPlaneTestCase):
    def _build_drag_rotate(self, wheel_delta) -> str:
        create_initial_test_setup()
        set_xplane_layer(0, {"export_type": "cockpit"})
        bpy.data.collections[0].xplane.is_exportable_collection = True

        A = create_datablock_empty(
            DatablockInfo("EMPTY", name="bone_r", collection="Layer 1")
        )
        B = create_datablock_mesh(
            DatablockInfo(
                "MESH", name="bone_n", parent_info=ParentInfo(A), collection="Layer 1"
            )
        )
        set_animation_data(A, R_2_FRAMES_45_Y_AXIS)
        set_manipulator_settings(
            B, MANIP_DRAG_ROTATE, manip_props={"wheel_delta": wheel_delta}
        )
        out = self.exportLayer(0)
        self.assertLoggerErrors(0)
        return out

    def test_drag_rotate_wheel_delta_exported(self):
        out = self._build_drag_rotate(0.5)
        self.assertTrue(
            any(
                line.split()[:1] == ["ATTR_manip_drag_rotate"]
                for line in out.splitlines()
            ),
            out,
        )
        self.assertEqual(["ATTR_manip_wheel 0.500"], _wheel_lines(out), out)

    def test_drag_rotate_wheel_zero_not_exported(self):
        out = self._build_drag_rotate(0.0)
        self.assertEqual([], _wheel_lines(out), out)

    def test_wheel_below_1050_not_exported(self):
        create_initial_test_setup()
        set_xplane_layer(0, {"export_type": "cockpit"})
        bpy.data.collections[0].xplane.is_exportable_collection = True

        A = create_datablock_mesh(
            DatablockInfo("MESH", name="bone_t", collection="Layer 1")
        )
        set_manipulator_settings(A, MANIP_DRAG_AXIS, manip_props={"wheel_delta": 0.5})
        set_animation_data(A, T_2_FRAMES_1_X)
        bpy.context.scene.xplane.version = VERSION_1040

        out = self.exportLayer(0)
        self.assertLoggerErrors(0)
        self.assertTrue(
            any(
                line.split()[:1] == ["ATTR_manip_drag_axis"]
                for line in out.splitlines()
            ),
            out,
        )
        self.assertEqual([], _wheel_lines(out), out)


runTestCases([TestDragRotateWheel])
