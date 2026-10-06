import os

import bpy
from io_xplane2blender.tests.test_creation_helpers import *
from io_xplane2blender.tests import *
from io_xplane2blender.xplane_constants import *

__dirname__ = os.path.dirname(__file__)

MULTIPLAYER = "sim/multiplayer/position/plane1_x"
NORMAL = "sim/cockpit2/engine/actuators/throttle_ratio_all"


def _translation_kfs(path):
    return (
        KeyframeInfo(idx=1, dataref_path=path, dataref_value=0.0, location=(0, 0, 0)),
        KeyframeInfo(idx=2, dataref_path=path, dataref_value=1.0, location=(1, 0, 0)),
    )


class TestMultiplayerDatarefs(XPlaneTestCase):
    def _setup(self):
        create_initial_test_setup()
        set_xplane_layer(0, {"export_type": "cockpit"})
        bpy.data.collections[0].xplane.is_exportable_collection = True

    def test_object_multiplayer_dataref_errors(self):
        self._setup()
        A = create_datablock_mesh(
            DatablockInfo("MESH", name="bone_t", collection="Layer 1")
        )
        set_animation_data(A, _translation_kfs(MULTIPLAYER))
        self.exportLayer(0)
        self.assertLoggerErrors(1)

    def test_bone_multiplayer_dataref_errors(self):
        self._setup()
        A = create_datablock_armature(
            DatablockInfo("ARMATURE", name="bone_r", collection="Layer 1")
        )
        B = create_datablock_mesh(
            DatablockInfo(
                "MESH",
                name="bone_t",
                parent_info=ParentInfo(
                    A, parent_type="BONE", parent_bone=A.data.bones[0].name
                ),
                collection="Layer 1",
            )
        )
        set_animation_data(A.pose.bones[0], _translation_kfs(MULTIPLAYER), A)
        self.exportLayer(0)
        self.assertLoggerErrors(1)

    def test_object_normal_dataref_no_errors(self):
        self._setup()
        A = create_datablock_mesh(
            DatablockInfo("MESH", name="bone_t", collection="Layer 1")
        )
        set_animation_data(A, _translation_kfs(NORMAL))
        out = self.exportLayer(0)
        self.assertLoggerErrors(0)
        self.assertTrue(
            any(
                "ANIM_trans_begin" in line and NORMAL in line
                for line in out.splitlines()
            ),
            out,
        )


runTestCases([TestMultiplayerDatarefs])
