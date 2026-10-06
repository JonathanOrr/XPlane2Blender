import bpy
from bpy_extras import anim_utils

from io_xplane2blender.tests import *
from io_xplane2blender.tests.test_creation_helpers import *


def _fcurves(animation_data):
    action = animation_data.action
    if hasattr(action, "layers"):  # Slotted Actions, Blender 4.4 and up
        channelbag = anim_utils.action_get_channelbag_for_slot(
            action, animation_data.action_slot
        )
        return list(channelbag.fcurves) if channelbag else []
    return list(action.fcurves)


class TestBoneKeyframeOperator(XPlaneTestCase):
    """Upstream #743: the keyframe button on the Bone tab seemed to do nothing"""

    def _add_keyframe_in_mode(self, mode: str) -> None:
        create_initial_test_setup()
        arm = create_datablock_armature(DatablockInfo("ARMATURE", name="Arm"))
        bpy.context.view_layer.objects.active = arm
        arm.select_set(True)
        bpy.ops.object.mode_set(mode="OBJECT")
        bone = arm.data.bones[0]
        arm.data.bones.active = bone
        bone.xplane.datarefs.add()
        bone.xplane.datarefs[0].path = "sim/test"
        bpy.ops.object.mode_set(mode=mode)

        self.assertEqual(
            bpy.ops.bone.add_xplane_dataref_keyframe(index=0), {"FINISHED"}
        )
        bpy.ops.object.mode_set(mode="OBJECT")

        # Bone animation data lives on the armature's data block, not the object
        self.assertIsNotNone(arm.data.animation_data)
        fcurves = _fcurves(arm.data.animation_data)
        self.assertEqual(
            [f.data_path for f in fcurves],
            [f'bones["{bone.name}"].xplane.datarefs[0].value'],
        )
        self.assertEqual(len(fcurves[0].keyframe_points), 1)

    def test_add_keyframe_object_mode(self) -> None:
        self._add_keyframe_in_mode("OBJECT")

    def test_add_keyframe_pose_mode(self) -> None:
        self._add_keyframe_in_mode("POSE")

    def test_add_keyframe_edit_mode(self) -> None:
        self._add_keyframe_in_mode("EDIT")


runTestCases([TestBoneKeyframeOperator])
