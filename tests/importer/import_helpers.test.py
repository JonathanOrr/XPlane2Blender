import math

from mathutils import Matrix, Vector

from io_xplane2blender.tests import *
from io_xplane2blender.xplane_importer import transforms as T
from io_xplane2blender.xplane_importer.defaults import (
    default_value,
    nearest_key_index,
    show_hide_visible,
)


class TestImportHelpers(XPlaneTestCase):
    def test_landing_gear_is_down_by_default(self) -> None:
        self.assertEqual(default_value("sim/flightmodel2/gear/deploy_ratio[2]"), 1.0)
        self.assertEqual(default_value("sim/aircraft/parts/acf_gear_deploy[0]"), 1.0)
        self.assertEqual(default_value("sim/flightmodel2/wing/flap1_deg[0]"), 0.0)
        self.assertEqual(default_value("some/custom/dataref"), 0.0)

    def test_nearest_key(self) -> None:
        self.assertEqual(nearest_key_index([-1.0, 0.0, 1.0], "x"), 1)
        self.assertEqual(nearest_key_index([0.0, 1.0], "sim/flightmodel2/gear/deploy_ratio"), 1)
        self.assertEqual(nearest_key_index([-20.0, 20.0], "x"), 0, "a tie takes the first key")
        self.assertEqual(nearest_key_index([5.0, 6.0], "x"), 0)

    def test_show_hide_at_the_default_value(self) -> None:
        self.assertTrue(show_hide_visible("show", -1, 1, "x"))
        self.assertFalse(show_hide_visible("show", 1, 2, "x"))
        self.assertTrue(show_hide_visible("hide", 1, 2, "x"))
        self.assertFalse(show_hide_visible("hide", 0, 0, "x"))
        # The gear is down by default, so "show when the gear is down" is visible and "hide" is not
        self.assertTrue(show_hide_visible("show", 0.5, 2, "sim/flightmodel2/gear/deploy_ratio[0]"))
        self.assertFalse(show_hide_visible("hide", 0.5, 2, "sim/flightmodel2/gear/deploy_ratio[0]"))

    def test_vectors_and_rotations_use_blenders_axes(self) -> None:
        self.assertEqual(T.vec_to_blender((1, 2, 3))[:], (1.0, -3.0, 2.0))
        # X-Plane's up axis is Blender's Z, and a quarter turn about it moves X to Y
        turned = T.matrix_to_blender(T.rotation_xp((0, 1, 0), 90)) @ Vector((1, 0, 0))
        self.assertAlmostEqual(turned.y, 1.0, places=5)
        moved = T.matrix_to_blender(T.translation_xp((1, 2, 3))).to_translation()
        self.assertEqual(tuple(round(c, 6) for c in moved), (1.0, -3.0, 2.0))

    def test_principal_axes(self) -> None:
        self.assertEqual(T.principal_axis((1, 0, 0)), (0, 1.0))
        self.assertEqual(T.principal_axis((0, 1, 0)), (2, 1.0))  # up
        self.assertEqual(T.principal_axis((0, 0, -1)), (1, 1.0))  # forward
        self.assertEqual(T.principal_axis((0, -1, 0)), (2, -1.0))
        self.assertEqual(T.principal_axis((1, 1, 0))[0], -1)
        self.assertEqual(T.principal_axis((0, 0, 0))[0], -1)

    def test_matrix_checks(self) -> None:
        self.assertTrue(T.is_identity(Matrix.Identity(4)))
        self.assertTrue(T.has_translation(Matrix.Translation((0, 0, 1))))
        self.assertFalse(T.has_rotation(Matrix.Translation((0, 0, 1))))
        self.assertTrue(T.has_rotation(Matrix.Rotation(math.radians(5), 4, "Z")))


runTestCases([TestImportHelpers])
