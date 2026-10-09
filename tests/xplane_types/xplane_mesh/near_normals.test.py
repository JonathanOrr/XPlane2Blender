import bpy
from mathutils import Vector

from io_xplane2blender.tests import XPlaneTestCase, runTestCases, test_creation_helpers


class TestNearNormals(XPlaneTestCase):
    def test_a_normal_stored_twice_is_one_vertex(self) -> None:
        # A center vertex in four faces that take turns between two normals: Blender keeps each face's normal in its
        # own space, and the same normal comes back a little different from each. It is one vertex in the OBJ
        bpy.ops.wm.read_homefile(use_empty=True)
        root = test_creation_helpers.create_datablock_collection("Near")
        mesh = bpy.data.meshes.new("Near")
        ring = [(1, 0, 0.3), (0, 1, -0.2), (-1, 0, 0.5), (0, -1, -0.4)]
        mesh.from_pydata([(0, 0, 0)] + ring, [], [(0, 1, 2), (0, 2, 3), (0, 3, 4), (0, 4, 1)])
        for polygon in mesh.polygons:
            polygon.use_smooth = True
        if hasattr(mesh, "use_auto_smooth"):
            mesh.use_auto_smooth = True  # Blender before 4.1 keeps custom normals only with it
        a, b = Vector((0.3, 0.2, 0.93)).normalized(), Vector((-0.25, 0.35, 0.9)).normalized()
        normals = [None] * len(mesh.loops)
        for polygon in mesh.polygons:
            for i in polygon.loop_indices:
                normals[i] = a if polygon.index % 2 == 0 else b
        mesh.normals_split_custom_set(normals)
        obj = bpy.data.objects.new("Near", mesh)
        root.objects.link(obj)
        bpy.context.scene.xplane.optimize = True
        bpy.context.view_layer.update()

        out = self.exportExportableRoot(root)
        self.assertLoggerErrors(0)
        vertices = [tuple(map(float, l.split()[1:9])) for l in out.splitlines() if l.startswith("VT")]
        center = [v for v in vertices if Vector(v[:3]).length < 1e-6]
        self.assertEqual(2, len(center), center)
        # Each ring vertex is in a face of each normal
        self.assertEqual(10, len(vertices))
        # Written in X-Plane's axes
        a, b = Vector((a.x, a.z, -a.y)), Vector((b.x, b.z, -b.y))
        for v in vertices:
            n = Vector(v[3:6])
            self.assertLess(min((n - a).length, (n - b).length), 1e-3, v)


runTestCases([TestNearNormals])
