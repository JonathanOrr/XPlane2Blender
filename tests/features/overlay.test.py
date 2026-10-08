"""
The viewport overlay's labels and click zone outlines (drawing itself needs a window, so only the data is checked)
"""

import math
from types import SimpleNamespace

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C
from io_xplane2blender.viewport import light_shapes
from io_xplane2blender.viewport import overlay as xplane_overlay
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout


class TestOverlay(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        test_creation_helpers.create_datablock_collection("Panel")

    def test_labels_say_what_a_click_does(self) -> None:
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "apu start", collection="Panel")
        )
        manip = obj.xplane.manip
        manip.enabled = True
        manip.type = C.MANIP_COMMAND
        self.assertEqual("Button", xplane_overlay.label_of(obj))
        manip.command = "a321/apu/start"
        self.assertEqual("Button: a321/apu/start", xplane_overlay.label_of(obj))
        manip.type = C.MANIP_TOGGLE
        manip.dataref1 = "a321/apu/master"
        self.assertEqual("Toggle: a321/apu/master", xplane_overlay.label_of(obj))
        self.assertEqual([obj], xplane_overlay.clickable(bpy.context))

    def test_zone_outline_has_twelve_edges_in_world_space(self) -> None:
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "zone", collection="Panel", location=(10, 0, 0))
        )
        bpy.context.view_layer.update()
        points = xplane_overlay.zone_lines(obj)
        self.assertEqual(24, len(points))
        self.assertTrue(all(p.x > 5 for p in points))

    def spot(self, name: str = "lamp", size: float = math.radians(60), rotation=(0, 0, 0)):
        data = bpy.data.lights.new(name, "SPOT")
        data.spot_size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.rotation_euler = rotation
        bpy.context.view_layer.update()
        return obj

    def test_a_spot_points_along_its_minus_z(self) -> None:
        down = self.spot()
        self.assertLess((light_shapes.direction(down) - Vector((0, 0, -1))).length, 1e-6)
        sideways = self.spot("sideways", rotation=(math.radians(90), 0, 0))
        self.assertLess((light_shapes.direction(sideways) - Vector((0, 1, 0))).length, 1e-6)

    def test_a_light_that_shines_all_around_has_no_direction_cone_or_tick(self) -> None:
        point = bpy.data.objects.new("bulb", bpy.data.lights.new("bulb", "POINT"))
        bpy.context.scene.collection.objects.link(point)
        self.assertIsNone(light_shapes.direction(point))
        self.assertEqual([], light_shapes.cone_lines(point))
        self.assertEqual([], light_shapes.screen_tick(None, point, Vector((10, 10, 0))))
        self.assertIsNone(light_shapes.direction(bpy.data.objects.new("empty", None)))

    def test_the_cone_ends_on_a_sphere_around_the_light(self) -> None:
        lamp = self.spot(size=math.radians(60))
        lamp.location = (1, 2, 3)
        bpy.context.view_layer.update()
        points = light_shapes.cone_lines(lamp)
        self.assertEqual(2 * light_shapes.EDGES + 2 * 24, len(points))
        apex = lamp.matrix_world.translation
        # Every edge goes from the light to a point of the circle, a slant length away
        for apex_point, end in zip(points[0:8:2], points[1:8:2]):
            self.assertLess((apex_point - apex).length, 1e-6)
            self.assertAlmostEqual(light_shapes.SLANT, (end - apex).length, places=5)
            self.assertLess(end.z, apex.z)
        # The wider the cone the wider the circle, and 180 degrees ends in the light's own plane
        wide = self.spot("wide", size=math.pi)
        flat = light_shapes.cone_lines(wide)
        self.assertAlmostEqual(0.0, max(abs(p.z - wide.matrix_world.translation.z) for p in flat), places=5)
        self.assertAlmostEqual(light_shapes.SLANT, max((p - wide.matrix_world.translation).length for p in flat), places=5)

    def test_the_tick_is_outside_the_ring_toward_where_the_spot_shines(self) -> None:
        lamp = self.spot(rotation=(math.radians(90), 0, 0))
        where = Vector((100.0, 100.0, 0.0))
        # A viewer who sees +Y going up the screen
        context = SimpleNamespace(region=object(), region_data=object())
        original = light_shapes.draw.screen_point
        light_shapes.draw.screen_point = lambda c, p: Vector((100.0, 100.0 + 50.0 * (p - lamp.matrix_world.translation).y))
        try:
            tick = light_shapes.screen_tick(context, lamp, where)
            self.assertEqual(2, len(tick))
            self.assertAlmostEqual(100.0, tick[0].x)
            self.assertAlmostEqual(100.0 + light_shapes.TICK_FROM, tick[0].y)
            self.assertAlmostEqual(100.0 + light_shapes.TICK_TO, tick[1].y)
            # Seen from straight on there is no direction on screen
            light_shapes.draw.screen_point = lambda c, p: Vector((100.0, 100.0))
            self.assertEqual([], light_shapes.screen_tick(context, lamp, where))
            light_shapes.draw.screen_point = lambda c, p: None
            self.assertEqual([], light_shapes.screen_tick(context, lamp, where))
        finally:
            light_shapes.draw.screen_point = original

    def test_typed_drag_directions_get_an_arrow(self) -> None:
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "trim wheel", collection="Panel")
        )
        manip = obj.xplane.manip
        manip.enabled, manip.type = True, C.MANIP_DRAG_AXIS
        manip.dx, manip.dy, manip.dz = 0, 0.1, 0
        bpy.context.view_layer.update()
        arrow = xplane_overlay.drag_arrow(obj)
        self.assertEqual(6, len(arrow))
        # X-Plane's up (y) is Blender's z
        self.assertAlmostEqual(0.1, (arrow[1] - arrow[0]).z)
        manip.autodetect_settings_opt_in = True
        self.assertEqual([], xplane_overlay.drag_arrow(obj))
        manip.type = C.MANIP_COMMAND
        self.assertEqual([], xplane_overlay.drag_arrow(obj))

    def test_overlay_popover_draws(self) -> None:
        layout = FakeLayout()
        xplane_overlay.overlay_popover(SimpleNamespace(layout=layout), SimpleNamespace(screen=bpy.data.screens[0]))
        self.assertIn("show_lever", layout.props())
        # Without a screen (background mode) there is nothing to draw
        xplane_overlay.overlay_popover(SimpleNamespace(layout=FakeLayout()), bpy.context)


runTestCases([TestOverlay])
