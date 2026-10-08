import os

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import (
    TempFolder,
    obj_text,
    write_file,
    write_png,
)
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.acf_parser import (
    AcfParseError,
    parse_acf_file,
    resolve_object_path,
)
from io_xplane2blender.xplane_importer.aircraft import import_aircraft
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport


def acf_text(objects: dict, extra: str = "", version: int = 1200) -> str:
    """objects maps an index to a dict of the _obja fields"""
    lines = [f"I\n{version} Version\nACF\n\nPROPERTIES_BEGIN"]
    lines.append("P acf/_descrip Test Plane")
    lines.append(extra) if extra else None
    for index, fields in objects.items():
        for key, value in fields.items():
            lines.append(f"P _obja/{index}/{key} {value}")
    lines.append("PROPERTIES_END\n")
    return "\n".join(lines)


def entry(file: str, flags: int = 1033, x=0.0, y=0.0, z=0.0, body=-1, wing=-1, gear=-1, hide="") -> dict:
    fields = {
        "_obj_flags": flags,
        "_v10_att_body": body,
        "_v10_att_file_stl": file,
        "_v10_att_gear": gear,
        "_v10_att_phi_ref": "0.0",
        "_v10_att_psi_ref": "0.0",
        "_v10_att_the_ref": "0.0",
        "_v10_att_wing": wing,
        "_v10_att_x_acf_prt_ref": x,
        "_v10_att_y_acf_prt_ref": y,
        "_v10_att_z_acf_prt_ref": z,
    }
    if hide:
        fields["_obj_hide_dataref"] = hide
    return fields


class TestImportAircraft(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        self.report = ImportReport()
        write_png(self.folder.join("objects", "paint.png"), rgba=(10, 20, 30, 255))
        write_png(self.folder.join("liveries", "Red", "objects", "paint.png"), rgba=(250, 0, 0, 255))
        for name in ("fuselage", "wing", "broken_wing", "easter_egg", "gear"):
            write_file(self.folder.join("objects", f"{name}.obj"), obj_text("", header="TEXTURE paint.png\n"))
        write_file(self.folder.join("objects", "lights.obj"), obj_text("LIGHT_NAMED beacon 0 1 0\n", tris=None))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def make_acf(self, objects: dict) -> str:
        return write_file(self.folder.join("Plane.acf"), acf_text(objects))

    def do_import(self, objects: dict, **kwargs):
        return import_aircraft(self.make_acf(objects), ImportOptions(), self.report, **kwargs)

    def names(self, collection):
        return sorted(c.name for c in collection.children)

    def test_every_object_becomes_a_collection(self) -> None:
        root = self.do_import({0: entry("fuselage.obj"), 1: entry("wing.obj")})
        self.assertEqual(root.name, "Test Plane")
        self.assertEqual(self.names(root), ["fuselage", "wing"])
        self.assertEqual(self.report.files_imported, 2)
        self.assertEqual(root["xplane_acf_version"], 1200)
        wing = root.children["wing"]
        self.assertEqual(wing["xplane_acf_object"], 1)
        self.assertEqual(wing["xplane_obj_flags"], 1033)
        self.assertFalse(wing.xplane.is_exportable_collection)

    def test_objects_are_placed_where_the_acf_says(self) -> None:
        root = self.do_import({0: entry("fuselage.obj", x=10.0, y=5.0, z=-20.0)})
        (mesh,) = [o for o in root.all_objects if o.type == "MESH"]
        # 10 ft right, 5 ft up, 20 ft forward, in meters, in Blender's axes
        self.assertEqual(tuple(round(v, 3) for v in mesh.matrix_world.translation), (3.048, 6.096, 1.524))

    def test_damage_and_attached_and_not_drawn_objects(self) -> None:
        objects = {
            0: entry("fuselage.obj"),
            1: entry("broken_wing.obj", 528, wing=0),
            2: entry("gear.obj", 24, gear=1),
            3: entry("easter_egg.obj", 0),
            4: entry("lights.obj", 0),
        }
        root = self.do_import(objects)
        self.assertEqual(self.names(root), ["easter_egg", "fuselage", "lights"])
        view_layer = bpy.context.view_layer.layer_collection.children["Test Plane"]
        self.assertTrue(view_layer.children["easter_egg"].exclude, "an object drawn nowhere is left out of the view layer")
        self.assertFalse(view_layer.children["fuselage"].exclude)
        self.assertFalse(view_layer.children["lights"].exclude, "lights are not geometry, flags 0 doesn't hide them")
        self.assertTrue(any("damage" in i for i in self.report.infos))
        self.assertTrue(any("attached" in i for i in self.report.infos))

    def test_options_bring_the_skipped_objects_back(self) -> None:
        objects = {0: entry("broken_wing.obj", 528, wing=0), 1: entry("gear.obj", 24, gear=1), 2: entry("easter_egg.obj", 0)}
        root = import_aircraft(
            self.make_acf(objects), ImportOptions(include_not_drawn=True), self.report, include_damage=True, include_attached=True
        )
        self.assertEqual(self.names(root), ["broken_wing", "easter_egg", "gear"])
        self.assertFalse(bpy.context.view_layer.layer_collection.children["Test Plane"].children["easter_egg"].exclude)

    def test_missing_objects_are_errors_but_the_rest_imports(self) -> None:
        root = self.do_import({0: entry("nothere.obj"), 1: entry("fuselage.obj")})
        self.assertEqual(self.names(root), ["fuselage"])
        self.assertEqual(self.report.files_failed, 1)
        self.assertTrue(any("nothere.obj" in e for e in self.report.errors))

    def test_a_livery_replaces_textures(self) -> None:
        def texture_of(root):
            (mesh,) = [o for o in root.all_objects if o.type == "MESH"]
            node = [n for n in mesh.data.materials[0].node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"][0]
            return os.path.normpath(bpy.path.abspath(node.image.filepath))

        plain = self.do_import({0: entry("fuselage.obj")})
        self.assertEqual(texture_of(plain), os.path.normpath(self.folder.join("objects", "paint.png")))
        create_initial_test_setup()
        red = self.do_import({0: entry("fuselage.obj")}, livery="Red")
        self.assertEqual(texture_of(red), os.path.normpath(self.folder.join("liveries", "Red", "objects", "paint.png")))
        # The OBJ is exported for the aircraft: it names its own texture, which X-Plane swaps for the livery's
        layer = red.children["fuselage"].xplane.layer
        self.assertEqual(os.path.normpath(layer.texture), os.path.normpath(self.folder.join("objects", "paint.png")))

    def test_an_unknown_livery_warns(self) -> None:
        self.do_import({0: entry("fuselage.obj")}, livery="Green")
        self.assertTrue(any("Green" in w for w in self.report.warnings))

    def test_the_hide_dataref_is_kept(self) -> None:
        root = self.do_import({0: entry("fuselage.obj", hide="sim/cockpit2/switches/custom_slider_on[22]")})
        self.assertEqual(root.children["fuselage"]["xplane_hide_dataref"], "sim/cockpit2/switches/custom_slider_on[22]")

    def test_bad_acf_is_reported(self) -> None:
        path = write_file(self.folder.join("Old.acf"), "I\n800 version\nACF\n")
        self.assertIsNone(import_aircraft(path, ImportOptions(), self.report))
        self.assertEqual(len(self.report.errors), 1)
        self.assertFalse(bpy.data.collections)

    def test_world_matrices_are_up_to_date_afterwards(self) -> None:
        body = "ANIM_begin\nANIM_trans 4 0 0 4 0 0\nTRIS 0 3\nANIM_end\n"
        write_file(self.folder.join("objects", "moved.obj"), obj_text(body, tris=None))
        root = self.do_import({0: entry("moved.obj", x=10.0)})
        (mesh,) = [o for o in root.all_objects if o.type == "MESH"]
        self.assertAlmostEqual(mesh.matrix_world.translation.x, 3.048 + 4.0, places=4)


runTestCases([TestImportAircraft])
