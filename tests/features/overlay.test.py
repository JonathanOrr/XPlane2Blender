"""
The viewport overlay's labels and click zone outlines (drawing itself needs a window, so only the data is checked)
"""

import math
from types import SimpleNamespace

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_light_tools
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

    def library_light(self, name: str, kind: str, params: str = "", blender_type: str = "SPOT"):
        obj = self.spot(name)
        obj.data.type = blender_type
        obj.data.xplane.type = kind
        obj.data.xplane.name = name
        obj.data.xplane.params = params
        return obj

    def test_the_reach_is_what_x_plane_gives_a_spill(self) -> None:
        reach = xplane_light_tools.throw_distance
        flood = self.spot("flood")
        flood.data.xplane.type = C.LIGHT_SPILL_CUSTOM
        flood.data.xplane.size = 2.5
        self.assertEqual(2.5, reach(flood))
        # A library spill is sized in meters too: the card's Light Size, or the third from last typed parameter
        automatic = self.library_light("airplane_landing_sp", C.LIGHT_AUTOMATIC)
        automatic.data.xplane.param_size = 7.0
        self.assertAlmostEqual(7.0, reach(automatic), places=5)
        automatic.data.xplane.param_size = 9.0
        self.assertAlmostEqual(9.0, reach(automatic), places=5)
        typed = self.library_light("airplane_landing_sp", C.LIGHT_PARAM, "1 1 1 0 12 0.9")
        self.assertAlmostEqual(12.0, reach(typed), places=5)
        named = self.library_light("pad_flood", C.LIGHT_NAMED)
        self.assertGreater(reach(named), 0.0)

    def test_there_is_no_reach_where_x_plane_gives_none(self) -> None:
        reach = xplane_light_tools.throw_distance
        # Lit by intensity: no cutoff
        self.assertIsNone(reach(self.library_light("airplane_landing_pm", C.LIGHT_AUTOMATIC)))
        # Glows light nothing, unknown names and unchosen lights are unknown, and lights not exported are not X-Plane's
        sprite = self.spot("sprite")
        sprite.data.xplane.type = C.LIGHT_CUSTOM
        self.assertIsNone(reach(sprite))
        self.assertIsNone(reach(self.library_light("not_in_lights_txt", C.LIGHT_NAMED)))
        self.assertIsNone(reach(self.library_light("", C.LIGHT_AUTOMATIC)))
        hidden = self.spot("scene only")
        hidden.data.xplane.type = C.LIGHT_NON_EXPORTING
        self.assertIsNone(reach(hidden))

    def test_a_spill_is_drawn_as_far_as_it_reaches(self) -> None:
        flood = self.spot("flood", size=math.radians(90))
        flood.data.xplane.type = C.LIGHT_SPILL_CUSTOM
        flood.data.xplane.size = 2.5
        apex = flood.matrix_world.translation
        points = light_shapes.shape(flood)
        self.assertAlmostEqual(2.5, max((p - apex).length for p in points), places=5)
        self.assertEqual("flood · reach 2.5 m", light_shapes.caption(flood, "flood"))

    def test_a_spot_without_a_reach_has_a_short_cone_that_says_it_only_shows_the_direction(self) -> None:
        lamp = self.library_light("airplane_landing_pm", C.LIGHT_AUTOMATIC)
        apex = lamp.matrix_world.translation
        self.assertAlmostEqual(light_shapes.SLANT, max((p - apex).length for p in light_shapes.shape(lamp)), places=5)
        self.assertEqual("landing · direction only", light_shapes.caption(lamp, "landing"))

    def test_a_light_that_shines_all_around_is_drawn_as_the_sphere_it_reaches(self) -> None:
        bulb = self.spot("bulb")
        bulb.data.type = "POINT"
        bulb.data.xplane.type = C.LIGHT_SPILL_CUSTOM
        bulb.data.xplane.size = 1.5
        center = bulb.matrix_world.translation
        points = light_shapes.shape(bulb)
        self.assertEqual(3 * 2 * 32, len(points))
        for p in points:
            self.assertAlmostEqual(1.5, (p - center).length, places=5)
        self.assertEqual("bulb · reach 1.5 m", light_shapes.caption(bulb, "bulb"))
        # Without a reach there is nothing to draw, and nothing to say but the name
        bulb.data.xplane.type = C.LIGHT_CUSTOM
        self.assertEqual([], light_shapes.shape(bulb))
        self.assertEqual("bulb", light_shapes.caption(bulb, "bulb"))

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
