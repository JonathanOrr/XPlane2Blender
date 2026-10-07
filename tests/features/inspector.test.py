"""
What the sidebar works out about objects: which file they export in, new files from a selection, textures from
materials, unfinished work and copying settings
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers


def mesh(name: str, collection: str) -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name, collection=collection)
    )


def textured_material(name: str, day: str, night: str = "") -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    for input_name, path in (("Base Color", day), ("Emission Color" if "Emission Color" in bsdf.inputs else "Emission", night)):
        if path:
            node = tree.nodes.new("ShaderNodeTexImage")
            node.image = bpy.data.images.new(path, 4, 4)
            node.image.filepath = path
            tree.links.new(node.outputs["Color"], bsdf.inputs[input_name])
    return material


class TestInspector(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        for name in ("Cockpit", "Organizing", "Spare"):
            test_creation_helpers.create_datablock_collection(name)
        bpy.data.collections["Cockpit"].xplane.is_exportable_collection = True

    def test_files_of(self) -> None:
        inside = mesh("inside", "Cockpit")
        outside = mesh("outside", "Spare")
        scene = bpy.context.scene
        self.assertEqual([bpy.data.collections["Cockpit"]], I.files_of(inside, scene))
        self.assertEqual([], I.files_of(outside, scene))
        self.assertEqual("Cockpit.obj", I.file_name(bpy.data.collections["Cockpit"]))

    def test_new_file_takes_objects_and_children_out_of_other_files(self) -> None:
        cup = mesh("cup", "Cockpit")
        handle = mesh("handle", "Organizing")
        handle.parent = cup
        bpy.data.collections["Organizing"].objects.link(cup)

        new = I.move_into_new_file([cup], "coffee_cup", bpy.context.scene)

        self.assertEqual({"cup", "handle"}, {o.name for o in new.objects})
        self.assertNotIn("cup", bpy.data.collections["Cockpit"].objects)
        # Collections that only organize the scene keep their objects
        self.assertIn("cup", bpy.data.collections["Organizing"].objects)
        self.assertTrue(new.xplane.is_exportable_collection)
        self.assertEqual("coffee_cup", new.xplane.layer.name)
        self.assertEqual(C.EXPORT_TYPE_AIRCRAFT, new.xplane.layer.export_type)

    def test_new_file_is_a_cockpit_when_something_is_clickable(self) -> None:
        button = mesh("button", "Spare")
        button.xplane.manip.enabled = True
        new = I.move_into_new_file([button], "buttons", bpy.context.scene)
        self.assertEqual(C.EXPORT_TYPE_COCKPIT, new.xplane.layer.export_type)

    def test_textures_come_from_the_materials_most_used(self) -> None:
        cockpit = bpy.data.collections["Cockpit"]
        common = textured_material("panel", "//panel.png", "//panel_LIT.png")
        rare = textured_material("odd", "//odd.png")
        for i in range(3):
            mesh(f"part{i}", "Cockpit").data.materials.append(common)
        mesh("odd", "Cockpit").data.materials.append(rare)
        cockpit.xplane.layer.texture_normal = "//kept_NML.png"

        filled = I.textures_from_materials(cockpit)

        layer = cockpit.xplane.layer
        self.assertEqual("//panel.png", layer.texture)
        self.assertEqual("//panel_LIT.png", layer.texture_lit)
        self.assertEqual("//kept_NML.png", layer.texture_normal)
        self.assertEqual({"texture", "texture_lit"}, set(filled))

    def test_coffee_cup_from_nothing_to_obj(self) -> None:
        # The newcomer's path: a textured mesh, New File From Selection, Export
        cup = mesh("coffee cup", "Spare")
        cup.data.materials.clear()
        cup.data.materials.append(textured_material("cup", "//cup.png"))

        new = I.move_into_new_file([cup], "coffee_cup", bpy.context.scene)
        out = self.exportExportableRoot(new.name)

        self.assertLoggerErrors(0)
        lines = [line.split() for line in out.splitlines() if line.strip()]
        self.assertIn(["TEXTURE", "cup.png"], lines)
        self.assertTrue(any(line[0] == "TRIS" for line in lines))

    def test_unfinished_work(self) -> None:
        button = mesh("button", "Cockpit")
        button.xplane.manip.enabled = True
        button.xplane.manip.type = C.MANIP_COMMAND_KNOB
        button.xplane.manip.positive_command = "a321/knob/up"
        button.xplane.lightLevel = True
        button.data.materials.clear()
        mesh("outside", "Spare")
        found = I.unfinished_in_files(bpy.context.scene)
        texts = [text for name, text in found if name == "button"]
        self.assertIn("Clickable: no counter-clockwise command yet", texts)
        self.assertIn("Glow: no dataref yet, left out", texts)
        self.assertIn("No material: exported with the default look", texts)
        self.assertFalse(any(name == "outside" for name, _ in found))
        outside = bpy.data.objects["outside"]
        self.assertIn("Not in an export file, so it is not exported", I.problems(outside, bpy.context.scene))

    def test_summary(self) -> None:
        button = mesh("button", "Cockpit")
        self.assertEqual(["Part"], I.summary(button))
        button.xplane.manip.enabled = True
        button.xplane.manip.type = C.MANIP_COMMAND
        button.xplane.lightLevel = True
        self.assertEqual(["Button", "Glows"], I.summary(button))

    def test_copying_click_settings_copies_detents_too(self) -> None:
        a, b = mesh("a", "Cockpit"), mesh("b", "Cockpit")
        a.xplane.manip.enabled = True
        a.xplane.manip.type = C.MANIP_DRAG_ROTATE_DETENT
        a.xplane.manip.tooltip = "Flaps"
        detent = a.xplane.manip.axis_detent_ranges.add()
        detent.start, detent.end, detent.height = 0.0, 1.0, 2.0
        self.assertTrue(I.copy_settings("CLICK", a, b))
        self.assertEqual(C.MANIP_DRAG_ROTATE_DETENT, b.xplane.manip.type)
        self.assertEqual("Flaps", b.xplane.manip.tooltip)
        self.assertEqual([(0.0, 1.0, 2.0)], [(d.start, d.end, d.height) for d in b.xplane.manip.axis_detent_ranges])


runTestCases([TestInspector])
