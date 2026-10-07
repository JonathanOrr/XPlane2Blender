import bpy

from io_xplane2blender.tests import *


class TestPropertyGroups(XPlaneTestCase):
    """Upstream #766 and #733 reported missing properties and buttons after installing"""

    def test_xplane_property_groups_are_registered(self) -> None:
        for datablock_type in (
            bpy.types.Object,
            bpy.types.Light,
            bpy.types.Material,
            bpy.types.Scene,
            bpy.types.Bone,
            bpy.types.Collection,
        ):
            with self.subTest(datablock_type=datablock_type.__name__):
                self.assertTrue(hasattr(datablock_type, "xplane"))

    def test_properties_exist_on_new_datablocks(self) -> None:
        bpy.ops.wm.read_homefile(use_factory_startup=True)
        scene = bpy.context.scene
        self.assertTrue(hasattr(scene.xplane, "optimize"))
        self.assertTrue(hasattr(scene.xplane, "xplane2blender_ver_history"))
        bpy.ops.object.armature_add()
        armature = bpy.context.object
        self.assertTrue(hasattr(armature.xplane, "datarefs"))
        self.assertTrue(hasattr(armature.data.bones[0].xplane, "datarefs"))
        # The dataref buttons need these to work from a blank file
        armature.xplane.datarefs.add()
        armature.data.bones[0].xplane.datarefs.add()
        self.assertEqual(len(armature.xplane.datarefs), 1)
        self.assertEqual(len(armature.data.bones[0].xplane.datarefs), 1)

    def test_xplane_panels_are_registered(self) -> None:
        # Object, bone, material, collection and scene settings are in the ui package
        for name in (
            "XPLANE_PT_object",
            "XPLANE_PT_bone",
            "XPLANE_PT_surface",
            "XPLANE_PT_collection",
            "XPLANE_PT_export",
        ):
            with self.subTest(panel=name):
                self.assertTrue(hasattr(bpy.types, name))


runTestCases([TestPropertyGroups])
