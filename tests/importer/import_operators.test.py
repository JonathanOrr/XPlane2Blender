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


def acf_with_one_object() -> str:
    return (
        "I\n1200 Version\nACF\n\nPROPERTIES_BEGIN\nP acf/_descrip Operator Plane\n"
        "P _obja/0/_obj_flags 1033\nP _obja/0/_v10_att_file_stl part.obj\n"
        "P _obja/0/_v10_att_body -1\nP _obja/0/_v10_att_wing -1\nP _obja/0/_v10_att_gear -1\n"
        "PROPERTIES_END\n"
    )


class TestImportOperators(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        write_png(self.folder.join("tex.png"))
        write_file(self.folder.join("part.obj"), obj_text("ATTR_manip_command button sim/x A tip\nTRIS 0 3\n", header="TEXTURE tex.png\n", tris=None))
        write_file(self.folder.join("other.obj"), obj_text("", header="TEXTURE tex.png\n"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def test_the_operators_are_in_the_import_menu(self) -> None:
        for idname in ("xplane_obj", "xplane_aircraft"):
            self.assertTrue(hasattr(bpy.ops.import_scene, idname))
        menu_entries = []

        class Probe:
            class layout:
                @staticmethod
                def operator(idname, text=""):
                    menu_entries.append((idname, text))

        from io_xplane2blender.xplane_importer import ops

        ops.menu_func_import(Probe, None)
        self.assertEqual(menu_entries, [("import_scene.xplane_aircraft", "X-Plane Aircraft (.acf)"), ("import_scene.xplane_obj", "X-Plane Object (.obj)")])

    def test_import_obj_operator(self) -> None:
        result = bpy.ops.import_scene.xplane_obj(filepath=self.folder.join("part.obj"))
        self.assertEqual(result, {"FINISHED"})
        self.assertIn("part", bpy.data.collections)
        self.assertEqual([o.xplane.manip.command for o in bpy.data.objects if o.type == "MESH"], ["sim/x"])

    def test_import_obj_operator_with_several_files(self) -> None:
        files = [{"name": "part.obj"}, {"name": "other.obj"}]
        result = bpy.ops.import_scene.xplane_obj(filepath=self.folder.join("part.obj"), directory=self.folder.path + os.sep, files=files)
        self.assertEqual(result, {"FINISHED"})
        self.assertTrue({"part", "other"} <= {c.name for c in bpy.data.collections})

    def test_import_obj_operator_options(self) -> None:
        bpy.ops.import_scene.xplane_obj(filepath=self.folder.join("part.obj"), import_manipulators=False, scale=2.0)
        mesh = [o for o in bpy.data.objects if o.type == "MESH"][0]
        self.assertFalse(mesh.xplane.manip.enabled)
        self.assertFalse(bpy.data.collections["part"].xplane.is_exportable_collection)
        self.assertAlmostEqual(max(v.co.x for v in mesh.data.vertices), 2.0, places=4)

    def test_a_file_that_fails_cancels(self) -> None:
        bad = write_file(self.folder.join("bad.obj"), "nope")
        # Operators that report an error raise it when they are called from Python
        with self.assertRaises(RuntimeError) as raised:
            bpy.ops.import_scene.xplane_obj(filepath=bad)
        self.assertIn("not an OBJ8 file", str(raised.exception))

    def test_import_aircraft_operator(self) -> None:
        path = write_file(self.folder.join("Plane.acf"), acf_with_one_object())
        result = bpy.ops.import_scene.xplane_aircraft(filepath=path)
        self.assertEqual(result, {"FINISHED"})
        self.assertEqual([c.name for c in bpy.data.collections["Operator Plane"].children], ["part"])

    def test_import_aircraft_operator_with_a_bad_file_cancels(self) -> None:
        path = write_file(self.folder.join("Old.acf"), "I\n800 version\nACF\n")
        with self.assertRaises(RuntimeError) as raised:
            bpy.ops.import_scene.xplane_aircraft(filepath=path)
        self.assertIn("binary", str(raised.exception))

    def test_everything_the_panel_draws_is_a_real_property(self) -> None:
        import inspect
        import re

        from io_xplane2blender.xplane_importer import ops

        for operator, cls in (
            (bpy.ops.import_scene.xplane_obj, ops.IMPORT_OT_xplane_obj),
            (bpy.ops.import_scene.xplane_aircraft, ops.IMPORT_OT_xplane_aircraft),
        ):
            properties = {p.identifier for p in operator.get_rna_type().properties}
            source = inspect.getsource(cls)
            drawn = set(re.findall(r'prop\(self, "(\w+)"', source))
            drawn |= set(re.findall(r'"(\w+)"', " ".join(re.findall(r"for name in \(([^)]*)\)", source))))
            self.assertTrue(drawn)
            self.assertFalse(drawn - properties, f"drawn but not properties: {drawn - properties}")

    def test_livery_choices_come_from_the_selected_aircraft(self) -> None:
        from io_xplane2blender.xplane_importer.ops import IMPORT_OT_xplane_aircraft, _livery_items

        path = write_file(self.folder.join("Plane.acf"), acf_with_one_object())
        os.makedirs(self.folder.join("liveries", "Red"))

        class Fake:
            filepath = path

        items = _livery_items(Fake, None)
        self.assertEqual([i[0] for i in items], ["DEFAULT", "Red"])


runTestCases([TestImportOperators])
