"""
Tidy Up: empties and light cones are drawn as small as what hangs on them, in a scene that is already built
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_display_sizes as sizes
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers


def box(name: str, size: float, parent=None) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(0, 0, 0), (size, 0, 0), (0, size, 0), (0, 0, size)], [], [])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    return obj


def empty(name: str, parent=None, size: float = 0.2) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_size = size
    bpy.context.scene.collection.objects.link(obj)
    obj.parent = parent
    return obj


def spot(name: str, energy: float = 0.0, **settings) -> bpy.types.Object:
    """A spot light that is off, unless it is given power"""
    data = bpy.data.lights.new(name, "SPOT")
    data.energy = energy
    for key, value in settings.items():
        setattr(data, key, value)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def select_only(*objects) -> None:
    for obj in bpy.context.scene.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)


class TestTidy(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()

    def test_a_chain_of_empties_takes_the_largest_part_below_it(self) -> None:
        top = empty("top")
        middle = empty("middle", top)
        box("small knob", 0.1, middle)
        box("bigger part", 0.3, top)
        found = sizes.part_sizes(o for o in bpy.data.objects if o.type == "MESH")
        self.assertAlmostEqual(0.3, found[top], places=5)
        self.assertAlmostEqual(0.1, found[middle], places=5)

    def test_empties_are_resized_to_a_fraction_of_their_part(self) -> None:
        holder = empty("holder")
        box("knob", 0.1, holder)
        bpy.ops.xplane.tidy_viewport()
        self.assertAlmostEqual(0.1 * sizes.FRACTION, holder.empty_display_size, places=5)

    def test_sizes_stay_within_limits_and_follow_the_unit(self) -> None:
        huge, tiny = empty("huge"), empty("tiny")
        box("fuselage", 40.0, huge)
        box("pin", 0.001, tiny)
        parts = sizes.part_sizes(o for o in bpy.data.objects if o.type == "MESH")
        sizes.fit_empty_sizes([huge, tiny], parts)
        self.assertAlmostEqual(sizes.MAX_SIZE, huge.empty_display_size, places=5)
        self.assertAlmostEqual(sizes.MIN_SIZE, tiny.empty_display_size, places=5)
        huge.empty_display_size = tiny.empty_display_size = 50.0
        sizes.fit_empty_sizes([huge, tiny], parts, unit=100.0)
        self.assertAlmostEqual(sizes.MIN_SIZE * 100, tiny.empty_display_size, places=3)
        self.assertAlmostEqual(sizes.MAX_SIZE * 100.0, huge.empty_display_size, places=3)

    def test_an_empty_with_nothing_on_it_is_small_unless_told_otherwise(self) -> None:
        bare = empty("bare", size=0.5)
        self.assertEqual(0, sizes.fit_empty_sizes([bare], {}, bare=None))
        self.assertAlmostEqual(0.5, bare.empty_display_size)
        self.assertEqual(1, sizes.fit_empty_sizes([bare], {}))
        self.assertAlmostEqual(sizes.BARE_SIZE, bare.empty_display_size, places=5)

    def test_an_empty_that_is_already_small_is_not_made_larger(self) -> None:
        tiny = empty("tiny", size=0.001)
        holder = empty("holder", size=0.002)
        box("big part", 0.2, holder)
        parts = sizes.part_sizes(o for o in bpy.data.objects if o.type == "MESH")
        self.assertEqual(0, sizes.fit_empty_sizes([tiny, holder], parts))
        self.assertAlmostEqual(0.001, tiny.empty_display_size, places=5)
        self.assertAlmostEqual(0.002, holder.empty_display_size, places=5)

    def test_attachment_points_keep_their_size(self) -> None:
        mount = empty("tablet mount", size=0.1)
        mount.xplane.special_empty_props.special_type = C.EMPTY_USAGE_MAGNET
        box("tablet", 0.01, mount)
        bpy.ops.xplane.tidy_viewport()
        self.assertAlmostEqual(0.1, mount.empty_display_size, places=5)

    def test_selected_only_leaves_the_rest(self) -> None:
        a, b = empty("a"), empty("b")
        box("part a", 0.1, a)
        box("part b", 0.1, b)
        select_only(a)
        bpy.ops.xplane.tidy_viewport(selected_only=True)
        self.assertAlmostEqual(0.1 * sizes.FRACTION, a.empty_display_size, places=5)
        self.assertAlmostEqual(0.2, b.empty_display_size, places=5)

    def test_spot_cones_get_a_short_custom_distance(self) -> None:
        plain = spot("plain")
        reach = spot("spill")
        reach.data.xplane.type = C.LIGHT_SPILL_CUSTOM
        reach.data.xplane.size = 0.7
        bpy.ops.xplane.tidy_viewport()
        self.assertTrue(plain.data.use_custom_distance)
        self.assertAlmostEqual(sizes.CONE_LENGTH, plain.data.cutoff_distance, places=5)
        self.assertAlmostEqual(0.7, reach.data.cutoff_distance, places=5)

    def test_a_light_that_lights_keeps_its_own_distance(self) -> None:
        lit = spot("lit", energy=50.0)
        reach = spot("lit spill", energy=50.0)
        reach.data.xplane.type = C.LIGHT_SPILL_CUSTOM
        reach.data.xplane.size = 3.0
        bpy.ops.xplane.tidy_viewport()
        self.assertFalse(lit.data.use_custom_distance)
        # How far a spill lights is how far its cone is drawn
        self.assertTrue(reach.data.use_custom_distance)
        self.assertAlmostEqual(3.0, reach.data.cutoff_distance, places=5)

    def test_turning_a_light_on_gives_its_distance_back_and_off_shortens_it_again(self) -> None:
        lamp = spot("lamp")
        sizes.tidy_lights([lamp])
        self.assertTrue(lamp.data.use_custom_distance)
        lamp.data.energy = 20.0
        self.assertEqual(1, sizes.tidy_lights([lamp]))
        self.assertFalse(lamp.data.use_custom_distance)
        self.assertIsNone(lamp.data.get(sizes.TIDIED))
        lamp.data.energy = 0.0
        self.assertEqual(1, sizes.tidy_lights([lamp]))
        self.assertTrue(lamp.data.use_custom_distance)
        self.assertAlmostEqual(sizes.CONE_LENGTH, lamp.data.cutoff_distance, places=5)

    def test_a_glow_sprite_is_never_lit_and_a_scene_light_is_left_alone(self) -> None:
        sprite = spot("sprite", energy=1.0)
        sprite.data.xplane.type = C.LIGHT_CUSTOM
        scene_light = spot("scene light")
        scene_light.data.xplane.type = C.LIGHT_NON_EXPORTING
        self.assertEqual(1, sizes.tidy_lights([sprite, scene_light]))
        self.assertTrue(sprite.data.use_custom_distance)
        self.assertFalse(scene_light.data.use_custom_distance)

    def test_a_distance_somebody_chose_is_kept(self) -> None:
        chosen = spot("chosen", use_custom_distance=True, cutoff_distance=12.0)
        self.assertEqual(0, sizes.tidy_lights([chosen]))
        self.assertAlmostEqual(12.0, chosen.data.cutoff_distance)

    def test_point_lights_and_shared_light_data(self) -> None:
        point = bpy.data.objects.new("point", bpy.data.lights.new("point", "POINT"))
        bpy.context.scene.collection.objects.link(point)
        one = spot("one")
        two = bpy.data.objects.new("two", one.data)
        bpy.context.scene.collection.objects.link(two)
        self.assertEqual(1, sizes.tidy_lights([point, one, two]))
        self.assertFalse(point.data.use_custom_distance)

    def test_running_it_twice_changes_nothing_more(self) -> None:
        holder = empty("holder")
        box("knob", 0.1, holder)
        spot("lamp")
        bpy.ops.xplane.tidy_viewport()
        parts = sizes.part_sizes(o for o in bpy.data.objects if o.type == "MESH")
        self.assertEqual(0, sizes.fit_empty_sizes(bpy.data.objects, parts))
        self.assertEqual(0, sizes.tidy_lights(bpy.data.objects))


runTestCases([TestTidy])
