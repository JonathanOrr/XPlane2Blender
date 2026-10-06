import itertools
import os

import bpy
from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import (
    TempFolder,
    obj_text,
    write_file,
    write_png,
)
from io_xplane2blender.tests.obj_evaluator import corners, max_distance
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file
from io_xplane2blender.xplane_importer.obj_parser import AnimNode, parse_obj

# A little house shape: a floor quad and a wall quad, so that every transform is visible in the corners
HOUSE_VT = (
    "VT 0 0 0 0 1 0 0 0\nVT 0 0 -1 0 1 0 0 1\nVT 1 0 -1 0 1 0 1 1\nVT 1 0 0 0 1 0 1 0\n"
    "VT 0 0 0 0 0 1 0 0\nVT 1 0 0 0 0 1 1 0\nVT 1 1 0 0 0 1 1 1\nVT 0 1 0 0 0 1 0 1\n"
)
HOUSE_IDX = "IDX10 0 1 2 0 2 3\nIDX10 4 5 6 4 6 7\n"


def all_datarefs(obj):
    keys = {}

    def visit(node):
        for op in node.ops:
            if not op.is_static:
                keys.setdefault(op.dataref, set()).update(k[0] for k in op.keys)
        for child in node.children:
            if isinstance(child, AnimNode):
                visit(child)

    visit(obj.root)
    return keys


def test_values(obj):
    """Several settings of the datarefs: every key, and between keys"""
    datarefs = all_datarefs(obj)
    sets = []
    for choice in range(4):
        values = {}
        for path, keys in datarefs.items():
            ordered = sorted(keys)
            if choice == 0:
                values[path] = 0.0
            elif choice == 1:
                values[path] = ordered[-1]
            elif choice == 2:
                values[path] = ordered[0]
            else:
                values[path] = (ordered[0] + ordered[-1]) / 2 + 0.123 * (ordered[-1] - ordered[0])
        sets.append(values)
    return sets


class TestImportRoundTrip(XPlaneTestCase):
    """Imports an OBJ, exports it with XPlane2Blender, and checks both look identical to X-Plane"""

    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        write_png(self.folder.join("tex.png"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def assert_round_trip(self, body: str, header: str = "TEXTURE tex.png\n") -> None:
        text = obj_text(body, header=header, vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        report = ImportReport()
        built = import_obj_file(path, ImportOptions(hide_default_hidden=False), report)
        self.assertIsNotNone(built, report.errors)
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        original = parse_obj(text)
        again = parse_obj(exported)
        for values in test_values(original):
            with self.subTest(values=values):
                expected = corners(original, values)
                actual = corners(again, values)
                self.assertEqual(expected.shape, actual.shape)
                self.assertLess(max_distance(expected, actual), 2e-3)

    def test_nothing_animated(self) -> None:
        self.assert_round_trip("TRIS 0 6\nTRIS 6 6\n")

    def test_static_transforms(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 2 1 -3 2 1 -3\nANIM_rotate 0 1 0 30 30\nANIM_rotate 1 0 0 -20 -20\n"
            "TRIS 0 6\nANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_rotate 0 0 1 15 15\nTRIS 6 6\nANIM_end\nANIM_end\n"
        )

    def test_rotation_about_a_principal_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 2 3 1 2 3\nANIM_rotate_begin 0 1 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_rotation_about_the_negative_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_rotate_begin 0 0 -1 sim/rot\nANIM_rotate_key -10 -45\nANIM_rotate_key 10 45\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_rotation_with_several_keys(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_rotate_begin 1 0 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 0.5 60\nANIM_rotate_key 1 30\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_translation(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans_begin sim/slide\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0.5 1 2\nANIM_trans_end\n"
            "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_rotation_about_an_arbitrary_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_rotate_begin 1 1 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 1 70\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_nested_animations(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 1 -2 0 1 -2\nANIM_rotate_begin 0 1 0 sim/outer\nANIM_rotate_key 0 0\nANIM_rotate_key 1 40\nANIM_rotate_end\n"
            "TRIS 0 6\n"
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_rotate_begin 1 0 0 sim/inner\nANIM_rotate_key 0 0\nANIM_rotate_key 1 -60\nANIM_rotate_end\n"
            "TRIS 6 6\nANIM_end\nANIM_end\n"
        )

    def test_rotate_then_translate_in_one_block(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_rotate_begin 0 0 1 sim/spin\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\n"
            "ANIM_trans_begin sim/push\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 1 0 0\nANIM_trans_end\n"
            "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_two_animated_meshes_share_nothing(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_rotate_begin 0 1 0 sim/a\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nTRIS 0 6\nANIM_end\n"
            "ANIM_begin\nANIM_trans_begin sim/b\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0 2 0\nANIM_trans_end\nTRIS 6 6\nANIM_end\n"
        )

    def test_show_and_hide_survive(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_show 0.5 1.5 sim/vis\nTRIS 0 6\nANIM_end\nANIM_begin\nANIM_hide 0.5 1.5 sim/vis\nTRIS 6 6\nANIM_end\n"
        )

    def test_lods_survive(self) -> None:
        body = "ATTR_LOD 0 500\nTRIS 0 6\nATTR_LOD 500 2000\nTRIS 6 6\n"
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        built = import_obj_file(path, ImportOptions(all_lods=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lods = [line.split() for line in exported.splitlines() if line.startswith("ATTR_LOD")]
        self.assertEqual(lods, [["ATTR_LOD", "0", "500"], ["ATTR_LOD", "500", "2000"]])
        again = parse_obj(exported)
        self.assertEqual([r.lod for r in again.iter_tris()], [(0.0, 500.0), (500.0, 2000.0)])

    def test_attributes_and_textures_survive(self) -> None:
        body = "ATTR_no_blend 0.4\nATTR_poly_os 2\nTRIS 0 6\nATTR_blend\nATTR_shiny_rat 0.3\nTRIS 6 6\n"
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        built = import_obj_file(path, ImportOptions(), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lines = [line.split() for line in exported.splitlines() if line.strip()]
        names = [line[0] for line in lines]
        self.assertIn("ATTR_no_blend", names)
        self.assertAlmostEqual(float(next(l for l in lines if l[0] == "ATTR_no_blend")[1]), 0.4, places=4)
        self.assertIn("ATTR_poly_os", names)
        self.assertIn("ATTR_shiny_rat", names)
        self.assertEqual(sum(1 for l in lines if l[0] == "TEXTURE"), 1)
        self.assertTrue(next(l for l in lines if l[0] == "TEXTURE")[1].endswith("tex.png"))

    def test_manipulators_and_light_levels_survive(self) -> None:
        body = (
            "ATTR_light_level 0 1 sim/lit\nATTR_manip_command button sim/cmd/a Do the A\nTRIS 0 6\n"
            "ATTR_manip_none\nATTR_light_level_reset\nATTR_manip_toggle button 1 0 sim/t Flip\nTRIS 6 6\n"
        )
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        built = import_obj_file(path, ImportOptions(), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lines = [line.split() for line in exported.splitlines() if line.strip()]
        self.assertIn(["ATTR_manip_command", "button", "sim/cmd/a", "Do", "the", "A"], lines)
        toggle = next(l for l in lines if l[0] == "ATTR_manip_toggle")
        self.assertEqual((toggle[1], float(toggle[2]), float(toggle[3]), toggle[4], toggle[5]), ("button", 1.0, 0.0, "sim/t", "Flip"))
        self.assertIn(["ATTR_light_level", "0", "1", "sim/lit"], lines)


runTestCases([TestImportRoundTrip])
