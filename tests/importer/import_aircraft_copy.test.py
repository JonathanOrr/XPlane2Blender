"""
An aircraft imported next to the saved .blend file: the files its OBJs use are copied to the same places below the
.blend's folder, each OBJ is exported where it was, and so the exported OBJs name their textures as the originals did
"""

import os

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import TempFolder, obj_text, write_file, write_png
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.aircraft import import_aircraft
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport

ACF = "I\n1200 Version\nACF\n\nPROPERTIES_BEGIN\nP acf/_descrip Test Plane\n{}\nPROPERTIES_END\n"


def acf_entry(index: int, file: str) -> str:
    return f"P _obja/{index}/_obj_flags 1033\nP _obja/{index}/_v10_att_file_stl {file}"


class TestImportAircraftCopy(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.temp = TempFolder()
        # Folders with spaces, as an aircraft in X-Plane 12 is
        self.aircraft = self.temp.join("X-Plane 12", "Aircraft", "Test Plane")
        self.project = self.temp.join("project")
        os.makedirs(self.project)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(self.project, "plane.blend"))
        self.report = ImportReport()
        write_png(self.in_aircraft("objects", "textures", "panel.png"))
        write_file(self.in_aircraft("objects", "textures", "panel.dds"), "DDS ")
        write_png(self.in_aircraft("objects", "textures", "panel_LIT.png"))
        header = "TEXTURE ../textures/panel.png\nTEXTURE_LIT ../textures/panel_LIT.png\n"
        write_file(self.in_aircraft("objects", "cockpit", "panel.obj"), obj_text("", header=header))

    def tearDown(self) -> None:
        self.temp.cleanup()
        super().tearDown()

    def in_aircraft(self, *parts: str) -> str:
        return os.path.join(self.aircraft, *parts)

    def in_project(self, *parts: str) -> str:
        return os.path.join(self.project, *parts)

    def do_import(self, *entries: str, **kwargs) -> bpy.types.Collection:
        acf = write_file(self.in_aircraft("Plane.acf"), ACF.format("\n".join(entries)))
        options = ImportOptions(make_exportable=True)
        return import_aircraft(acf, options, self.report, copy_to=self.project, **kwargs)

    def test_textures_are_copied_to_the_same_places(self) -> None:
        self.do_import(acf_entry(0, "cockpit/panel.obj"))

        for name in ("panel.png", "panel.dds", "panel_LIT.png"):
            self.assertTrue(os.path.isfile(self.in_project("objects", "textures", name)), name)
        self.assertTrue(any("Copied 3" in i for i in self.report.infos), self.report.infos)

    def test_each_obj_is_exported_where_it_was_and_names_the_copies(self) -> None:
        root = self.do_import(acf_entry(0, "cockpit/panel.obj"))

        layer = root.children["panel"].xplane.layer
        self.assertEqual("objects/cockpit/panel", layer.name)
        self.assertEqual("//objects/textures/panel.png", layer.texture)
        (mesh,) = [o for o in root.all_objects if o.type == "MESH"]
        image = [n for n in mesh.data.materials[0].node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"][0].image
        self.assertEqual(
            os.path.normpath(self.in_project("objects", "textures", "panel.png")),
            os.path.normpath(bpy.path.abspath(image.filepath)),
        )

    def test_the_exported_obj_names_its_textures_as_the_original(self) -> None:
        self.do_import(acf_entry(0, "cockpit/panel.obj"))

        self.assertEqual({"FINISHED"}, bpy.ops.export.xplane_obj(filepath=".", export_is_relative=True))

        with open(self.in_project("objects", "cockpit", "panel.obj")) as f:
            lines = [line.split() for line in f]
        self.assertIn(["TEXTURE", "../textures/panel.png"], lines)
        self.assertIn(["TEXTURE_LIT", "../textures/panel_LIT.png"], lines)

    def test_files_already_there_are_kept(self) -> None:
        edited = write_png(self.in_project("objects", "textures", "panel.png"), rgba=(1, 2, 3, 255))
        with open(edited, "rb") as f:
            before = f.read()

        self.do_import(acf_entry(0, "cockpit/panel.obj"))

        with open(edited, "rb") as f:
            self.assertEqual(before, f.read())
        self.assertTrue(any("kept as they are" in i for i in self.report.infos), self.report.infos)

    def test_a_livery_is_copied_to_its_own_place(self) -> None:
        write_png(self.in_aircraft("liveries", "Red", "objects", "textures", "panel.png"), rgba=(250, 0, 0, 255))

        root = self.do_import(acf_entry(0, "cockpit/panel.obj"), livery="Red")

        self.assertTrue(os.path.isfile(self.in_project("liveries", "Red", "objects", "textures", "panel.png")))
        # The OBJ still names the aircraft's own texture, which X-Plane swaps for the livery's
        self.assertEqual("//objects/textures/panel.png", root.children["panel"].xplane.layer.texture)

    def test_a_texture_outside_the_aircraft_is_used_where_it_is(self) -> None:
        shared = write_png(self.temp.join("shared", "metal.png"))
        write_file(self.in_aircraft("objects", "rail.obj"), obj_text("", header=f"TEXTURE {shared}\n"))

        root = self.do_import(acf_entry(0, "rail.obj"))

        self.assertEqual(os.path.normpath(shared), os.path.normpath(root.children["rail"].xplane.layer.texture))
        self.assertTrue(any("not in the aircraft's folder" in w for w in self.report.warnings), self.report.warnings)

    def test_importing_an_aircraft_needs_a_saved_blend_file(self) -> None:
        self.assertTrue(bpy.ops.import_scene.xplane_aircraft.poll())
        bpy.ops.wm.read_homefile(use_empty=True)
        self.assertFalse(bpy.ops.import_scene.xplane_aircraft.poll())


runTestCases([TestImportAircraftCopy])
