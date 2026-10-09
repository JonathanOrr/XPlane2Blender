"""Round trips found on a third-party airliner: a part with one LOD, and normals next to faces with no area"""

import numpy as np

from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import TempFolder, obj_text, write_file, write_png
from io_xplane2blender.tests.obj_evaluator import corner_normals, corners, max_distance
from io_xplane2blender.tests.roundtrip_helpers import HOUSE_IDX, HOUSE_VT
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file
from io_xplane2blender.xplane_importer.obj_parser import parse_obj

# Six faces around a corner (Blender's axes and winding). The last two have no area and share the normal of a face
# that has one: Blender works a fan's normals out from its faces, so turning the mesh moved that face's normal by up
# to 50 degrees (found on an airliner's walls)
_V = [(0, 0, 0), (0.07, 0, 0), (0.07, 0, -0.03), (0, 0, -0.03), (0, -0.01, 0), (-0.13, 0, 0), (0.2, 0, 0)]
_F = [(0, 1, 2), (0, 2, 3), (4, 0, 3), (4, 5, 0), (1, 0, 6), (0, 5, 6)]
_S = (-0.0453, -0.999, 0)
_N = [
    [(0, 0, -1)] * 3,
    [(0, 0, -1)] * 3,
    [(-1, 0, 0)] * 3,
    [(0, -1, 0), _S, (0, -1, 0)],
    [(0, 1, 0), (0, 1, 0), (-_S[0], _S[1], 0)],
    [(0, -1, 0), _S, (0, -1, 0)],
]

# A static turn, then a knob's turn: the importer folds the static one into the mesh
_TURNED = (
    "ANIM_begin\n"
    "ANIM_trans 0.2 1 3 0.2 1 3 0 0 no_ref\n"
    "ANIM_rotate 0.3 0.9 0.1 37 37 0 0 no_ref\n"
    "ANIM_rotate_begin 1 0 0 sim/test/knob\n"
    "ANIM_rotate_key 0 0\n"
    "ANIM_rotate_key 1 90\n"
    "ANIM_rotate_end\n"
    "{tris}"
    "ANIM_end\n"
)


# Four faces around a corner that fold back on each other (Blender's axes and winding): their directions cancel, and
# Blender kept no normal at the center (found on a pilot figure's collar)
_FOLD_V = [(0, 0, 0), (0, 0.5, 0), (0, 0.5, -1), (0, 1, 0), (0.5, 0.5, -1)]
_FOLD_F = [(0, 2, 1), (0, 3, 2), (0, 3, 4), (0, 4, 1)]
_FOLD_N = [[(0.7071, 0, -0.7071)] * 3] * 4


def _fan(V=_V, F=_F, N=_N) -> tuple:
    """The fan as VT and IDX lines, in X-Plane's axes (x, z, -y) and clockwise winding"""
    lines = []
    for face, normals in zip(F, N):
        for i in reversed(range(3)):
            (x, y, z), n = V[face[i]], np.array(normals[i], dtype=float)
            n /= np.linalg.norm(n)
            lines.append("VT\t" + "\t".join(f"{v:.6f}" for v in (x, z, -y, n[0], n[2], -n[1], 0.5, 0.5)))
    count = 3 * len(F)
    indices = "IDX10\t0 1 2 3 4 5 6 7 8 9\n" + "".join(f"IDX\t{i}\n" for i in range(10, count))
    return "\n".join(lines) + "\n", indices


class TestImportRoundTripShapes(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        write_png(self.folder.join("tex.png"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def _export(self, text: str, all_lods: bool = True) -> str:
        path = write_file(self.folder.join("part.obj"), text)
        report = ImportReport()
        built = import_obj_file(path, ImportOptions(make_exportable=True, all_lods=all_lods), report)
        self.assertIsNotNone(built, report.errors)
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        return exported

    def test_a_single_lod_keeps_its_range(self) -> None:
        # An airliner's crew rest is drawn within 5 m only, with "All LODs" on or off
        text = obj_text("ATTR_LOD 0 5\nTRIS 0 6\n", header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        for all_lods in (True, False):
            with self.subTest(all_lods=all_lods):
                again = parse_obj(self._export(text, all_lods))
                self.assertEqual([(0.0, 5.0)], [tuple(map(float, lod)) for lod in again.lods])
                self.assertLess(max_distance(corners(parse_obj(text)), corners(again)), 1e-3)

    def test_normals_next_to_faces_with_no_area_survive_turns(self) -> None:
        vertices, indices = _fan()
        text = obj_text(_TURNED.format(tris="TRIS 0 18\n"), header="TEXTURE tex.png\n", vertices=vertices, indices=indices, tris=None)
        # The faces with no area draw nothing: only the four with one must come back
        drawn = obj_text(_TURNED.format(tris="TRIS 0 12\n"), header="TEXTURE tex.png\n", vertices=vertices, indices=indices, tris=None)
        expected = corner_normals(parse_obj(drawn))
        actual = corner_normals(parse_obj(self._export(text)))
        self.assertEqual(12, len(expected))
        for row in expected:
            with self.subTest(corner=np.round(row[:3], 3).tolist()):
                self.assertLess(min(float(np.abs(row - other).max()) for other in actual), 1e-3)

    def test_normals_where_faces_fold_back_are_kept(self) -> None:
        vertices, indices = _fan(_FOLD_V, _FOLD_F, _FOLD_N)
        text = obj_text("TRIS 0 12\n", header="TEXTURE tex.png\n", vertices=vertices, indices=indices, tris=None)
        expected = corner_normals(parse_obj(text))
        actual = corner_normals(parse_obj(self._export(text)))
        self.assertEqual(12, len(expected))
        for row in expected:
            with self.subTest(corner=np.round(row[:3], 3).tolist()):
                self.assertLess(min(float(np.abs(row - other).max()) for other in actual), 1e-3)


runTestCases([TestImportRoundTripShapes])
