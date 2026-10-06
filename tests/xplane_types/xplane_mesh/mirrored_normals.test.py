import bpy
from mathutils import Vector

from io_xplane2blender.tests import XPlaneTestCase, runTestCases, test_creation_helpers


class TestMirroredNormals(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        bpy.ops.wm.read_homefile(use_empty=True)
        self.root = test_creation_helpers.create_datablock_collection("Mirrors")
        self.original = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "A", collection=self.root)
        )
        self.mirror = bpy.data.objects.new("B", self.original.data)
        self.root.objects.link(self.mirror)
        self.mirror.location.x = 5
        self.mirror.scale = (-1, 2, 3)
        self.assertIs(self.original.data, self.mirror.data)

    def _check_export(self, custom_normals=False):
        bpy.context.view_layer.update()
        out = self.exportExportableRoot(self.root)
        self.assertLoggerErrors(0)
        vertices, indices, blocks = [], [], []
        for line in out.splitlines():
            tokens = line.split()
            if not tokens:
                continue
            if tokens[0] == "VT":
                vertices.append(tuple(map(float, tokens[1:9])))
            elif tokens[0] in {"IDX", "IDX10"}:
                indices.extend(map(int, tokens[1:]))
            elif tokens[0] == "TRIS":
                blocks.append(tuple(map(int, tokens[1:3])))

        self.assertEqual(2, len(blocks))
        for start, count in blocks:
            with self.subTest(block=start):
                verts = [vertices[i] for i in set(indices[start : start + count])]
                centroid = sum((Vector(v[:3]) for v in verts), Vector()) / len(verts)
                # Same "normals away from centroid" metric as .work/tools/obj_normals.py.
                away = sum(
                    (Vector(v[:3]) - centroid).dot(Vector(v[3:6])) > 0 for v in verts
                )
                self.assertEqual(
                    len(verts), away, f"TRIS {start}: {away}/{len(verts)} outward"
                )
                if custom_normals:
                    for vertex in verts:
                        expected = Vector(vertex[:3]) - centroid
                        expected.x *= 2
                        if start:
                            expected.x /= self.mirror.scale.x**2
                            expected.y /= self.mirror.scale.z**2
                            expected.z /= self.mirror.scale.y**2
                        expected.normalize()
                        self.assertLess((Vector(vertex[3:6]) - expected).length, 0.001)
                for t in range(start, start + count, 3):
                    a, b, c = (vertices[i] for i in indices[t : t + 3])
                    geometric_normal = (Vector(b[:3]) - Vector(a[:3])).cross(
                        Vector(c[:3]) - Vector(a[:3])
                    )
                    normal = sum((Vector(v[3:6]) for v in (a, b, c)), Vector())
                    self.assertLess(
                        geometric_normal.dot(normal), 0, "OBJ winding must be CW"
                    )

    def test_linked_duplicate_flat_normals(self):
        self._check_export()

    def test_linked_duplicate_smooth_normals(self):
        for polygon in self.original.data.polygons:
            polygon.use_smooth = True
        self._check_export()

    def test_linked_duplicate_custom_normals(self):
        mesh = self.original.data
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        if hasattr(mesh, "use_auto_smooth"):
            mesh.use_auto_smooth = True
        normals = []
        for loop in mesh.loops:
            normal = mesh.vertices[loop.vertex_index].co.copy()
            normal.x *= 2
            normals.append(normal.normalized())
        mesh.normals_split_custom_set(normals)
        self._check_export(custom_normals=True)

    def test_negative_scale_parent(self):
        parent = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Parent", collection=self.root)
        )
        parent.scale = (-1, 2, 3)
        self.mirror.scale = (1, 1, 1)
        self.mirror.parent = parent
        self._check_export()

    def test_mirrored_child_under_animated_parent(self):
        parent = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Parent", collection=self.root)
        )
        self.mirror.parent = parent
        test_creation_helpers.set_animation_data(
            parent,
            [
                test_creation_helpers.KeyframeInfo(
                    idx=1,
                    dataref_path="sim/test/mirror",
                    dataref_value=0,
                    location=(0, 0, 0),
                ),
                test_creation_helpers.KeyframeInfo(
                    idx=2,
                    dataref_path="sim/test/mirror",
                    dataref_value=1,
                    location=(0, 1, 0),
                ),
            ],
        )
        self._check_export()

    def test_two_reflections_keep_outward_normals(self):
        parent = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Parent", collection=self.root)
        )
        parent.scale.x = -1
        self.mirror.parent = parent
        self._check_export()


runTestCases([TestMirroredNormals])
