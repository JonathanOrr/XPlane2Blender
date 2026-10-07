"""
The pie menu, the X-Plane Copy tool, the X-Plane workspace and the detail texture preview
(what needs a window, such as clicking in the viewport or switching workspaces, is not run)
"""

import os
from types import SimpleNamespace

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout
from io_xplane2blender.viewport import detail_preview, pie, tool, workspace


def save_image(name: str) -> str:
    path = os.path.join(get_tmp_folder(), f"{name}.png")
    image = bpy.data.images.new(name, 4, 4)
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)
    return path


def textured_material(name: str):
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    texture = tree.nodes.new("ShaderNodeTexImage")
    texture.image = bpy.data.images.load(save_image(f"{name}_base"))
    tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
    return material, bsdf, texture


class TestViewportTools(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        test_creation_helpers.create_datablock_collection("Panel")
        self.layer = bpy.data.collections["Panel"].xplane.layer
        bpy.data.collections["Panel"].xplane.is_exportable_collection = True
        self.obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "panel", collection="Panel")
        )
        bpy.context.view_layer.objects.active = self.obj

    def test_pie_menu_draws(self) -> None:
        layout = FakeLayout()
        context = SimpleNamespace(screen=bpy.data.screens[0], object=self.obj)
        pie.XPLANE_MT_pie.draw(SimpleNamespace(layout=layout), context)
        self.assertIn("scene.export_to_relative_dir", layout.operators())
        self.assertIn("xplane.check_in_viewport", layout.operators())
        self.assertIn("show_lever", layout.props())
        # Key This Pose is offered for animated objects only
        self.assertNotIn("xplane.key_pose", layout.operators())
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM)
        layout = FakeLayout()
        pie.XPLANE_MT_pie.draw(SimpleNamespace(layout=layout), context)
        self.assertIn("xplane.key_pose", layout.operators())
        pie.XPLANE_MT_pie.draw(
            SimpleNamespace(layout=FakeLayout()),
            SimpleNamespace(screen=None, object=None),
        )
        pie.XPLANE_MT_animate.draw(SimpleNamespace(layout=FakeLayout()), bpy.context)

    def test_check_in_viewport(self) -> None:
        self.obj.xplane.lightLevel = True
        self.assertEqual({"FINISHED"}, bpy.ops.xplane.check_in_viewport())
        self.assertTrue(bpy.context.window_manager.xplane_panels.check_items)

    def test_copy_tool_copies_the_chosen_settings(self) -> None:
        self.obj.xplane.manip.enabled = True
        self.obj.xplane.manip.type = C.MANIP_COMMAND
        self.obj.xplane.manip.command = "a321/button"
        other = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "other", collection="Panel")
        )
        self.assertEqual(1, tool.copy_to(self.obj, other, {"CLICK"}))
        self.assertEqual("a321/button", other.xplane.manip.command)
        empty = bpy.data.objects.new("empty", None)
        self.assertEqual(0, tool.copy_to(self.obj, empty, {"CLICK"}))
        self.assertTrue(hasattr(bpy.types, tool.XPLANE_OT_copy_tool_click.__name__))

    def test_workspace_set_up(self) -> None:
        space = bpy.data.workspaces[0]
        workspace.set_up(space)
        for screen in space.screens:
            self.assertTrue(screen.xplane_view.show_click_zones)
            self.assertTrue(screen.xplane_view.show_lever)
        self.assertFalse(
            workspace.XPLANE_OT_workspace.poll(SimpleNamespace(window=None))
        )

    def test_detail_preview_goes_in_and_comes_out(self) -> None:
        material, bsdf, base = textured_material("paint")
        self.obj.data.materials.append(material)
        self.layer.file_decal1 = save_image("grain")
        self.layer.rgb_decal1_constant = 1.0
        self.layer.file_normal_decal1 = save_image("grain_nml")
        self.layer.normal_decal1_red_key = 0.5

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.detail_preview())
        self.assertTrue(
            detail_preview.is_preview(bsdf.inputs["Base Color"].links[0].from_node)
        )
        self.assertTrue(
            detail_preview.is_preview(bsdf.inputs["Normal"].links[0].from_node)
        )
        # X-Plane normal maps keep only X and Y, Z is rebuilt
        self.assertTrue(any(n.name.startswith("XP2B Detail Normal Z") for n in material.node_tree.nodes))
        # From Materials still finds the base texture behind the preview
        self.assertEqual(base.image, I.material_images(material)["texture"])
        # Showing it again replaces it
        count = len(material.node_tree.nodes)
        bpy.ops.xplane.detail_preview()
        self.assertEqual(count, len(material.node_tree.nodes))

        bpy.ops.xplane.detail_preview(remove=True)
        self.assertEqual(base, bsdf.inputs["Base Color"].links[0].from_node)
        self.assertFalse(bsdf.inputs["Normal"].is_linked)
        self.assertFalse(
            any(detail_preview.is_preview(n) for n in material.node_tree.nodes)
        )

    def test_each_decal_reads_its_own_modulator_channel(self) -> None:
        material, bsdf, _ = textured_material("panel")
        self.obj.data.materials.append(material)
        # Like Laminar's A330 cockpit: leather then plastic, both keyed by the modulator
        self.layer.texture_modulator = save_image("control")
        for i, name in ((1, "leather"), (2, "plastic")):
            setattr(self.layer, f"file_normal_decal{i}", save_image(name))
            setattr(self.layer, f"normal_decal{i}_modulator", 1.0)
        self.assertTrue(detail_preview.add_preview(material, self.layer, []))
        nodes = material.node_tree.nodes

        def modulator_channel(i):
            strength = nodes[f"XP2B Detail Normal {i}"].inputs["Strength"].links[0].from_node
            key = strength.inputs[0].links[0].from_node
            return key.inputs[0].links[0].from_socket

        channels = nodes["XP2B Detail Modulator Channels"].outputs
        self.assertEqual(channels[0], modulator_channel(1))
        self.assertEqual(channels[1], modulator_channel(2))

    def test_detail_preview_skips_what_it_cannot_show(self) -> None:
        material, bsdf, _ = textured_material("plain")
        self.obj.data.materials.append(material)
        report = []
        self.assertFalse(detail_preview.add_preview(material, self.layer, report))
        self.layer.file_decal1 = "//missing.png"
        self.layer.file_decal2 = "//lib.dcl"
        self.assertFalse(detail_preview.add_preview(material, self.layer, report))
        self.assertEqual(2, len(report), report)
        self.assertFalse(detail_preview.remove_preview(material))


runTestCases([TestViewportTools])
