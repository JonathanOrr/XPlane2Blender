"""
The numbers an X-Plane light shares with its Blender light are kept equal, whichever side is changed: Intensity and
Power, Reach and Custom Distance, and for typed lights the cone and the color
"""

import math

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_light_sync as sync
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.xplane_importer.lights import WATTS_PER_CANDELA
from io_xplane2blender.xplane_light_sync import links
from io_xplane2blender.xplane_utils import xplane_light_params as lp
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as lights_txt

PM = "airplane_landing_pm"  # R G B INDEX INTENSITY DX DY DZ WIDTH, lit by its intensity
SP = "airplane_landing_sp"  # R G B INDEX SIZE WIDTH, a spill sized in meters
BILLBOARD = "airplane_strobe_dir"  # an older light: its direction is as long as one minus its width


def make(name: str, kind: str, lights_name: str = "", params: str = "", type_: str = "SPOT", select: bool = True):
    data = bpy.data.lights.new(name, type_)
    data.xplane.type = kind
    data.xplane.name = lights_name
    data.xplane.params = params
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    if select:
        for other in bpy.context.scene.objects:
            other.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    return data


def line(light_name: str, **values) -> str:
    formal = list(lights_txt.get_parsed_light(light_name).light_param_def)
    return lp.update_line(lp.default_line(formal), formal, values)


def settled(data: bpy.types.Light) -> None:
    """Writes down the Blender side as it is, as the handler does the first time it looks at a light"""
    sync.forget()
    sync.blender_changed()
    sync.remember(data)


class TestLightSync(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        lights_txt.parse_lights_file()
        sync.forget()

    # ---- Intensity and Power ------------------------------------------------------------------------------
    def test_changing_the_intensity_changes_the_power_of_a_light_that_is_on(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 100.0
        data.xplane.param_intensity_new = 40000.0
        self.assertAlmostEqual(40000.0 * WATTS_PER_CANDELA, data.energy, places=3)

    def test_a_light_that_is_off_stays_off(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 0.0
        data.xplane.param_intensity_new = 40000.0
        self.assertEqual(0.0, data.energy)

    def test_changing_the_power_changes_the_intensity(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 500.0
        settled(data)
        data.energy = 800.0
        sync.blender_changed()
        self.assertAlmostEqual(800.0 / WATTS_PER_CANDELA, data.xplane.param_intensity_new, places=1)
        self.assertAlmostEqual(800.0, data.energy, places=3)

    def test_a_light_is_never_changed_by_being_looked_at(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 300.0
        data.xplane.param_intensity_new = 20000.0
        data.energy = 300.0
        sync.forget()  # As when a file has just been opened
        sync.blender_changed()
        sync.blender_changed()
        self.assertEqual(20000.0, data.xplane.param_intensity_new)

    def test_switching_a_light_off_does_not_take_its_intensity_away(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 400.0
        settled(data)
        data.energy = 0.0
        sync.blender_changed()
        self.assertEqual(20000.0, data.xplane.param_intensity_new)

    def test_the_power_is_not_taken_in_for_unselected_lights(self) -> None:
        other = make("other", C.LIGHT_AUTOMATIC, PM)
        other.energy = 300.0
        settled(other)
        make("selected", C.LIGHT_AUTOMATIC, PM)  # Selecting it unselects the first
        other.energy = 900.0
        sync.blender_changed()
        self.assertEqual(20000.0, other.xplane.param_intensity_new)

    def test_the_handler_does_its_work_after_a_change(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 300.0
        bpy.context.view_layer.update()
        data.energy = 600.0
        bpy.context.view_layer.update()
        self.assertAlmostEqual(600.0 / WATTS_PER_CANDELA, data.xplane.param_intensity_new, places=1)

    def test_what_a_preview_multiplied_the_power_by_is_taken_out_again(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data[sync.STRENGTH] = 2.0
        data.energy = 100.0
        data.xplane.param_intensity_new = 1000.0
        self.assertAlmostEqual(1000.0 * WATTS_PER_CANDELA * 2.0, data.energy, places=3)
        settled(data)
        data.energy = 400.0
        sync.blender_changed()
        self.assertAlmostEqual(400.0 / WATTS_PER_CANDELA / 2.0, data.xplane.param_intensity_new, places=1)

    def test_lights_without_an_intensity_have_no_such_link(self) -> None:
        self.assertEqual([], [l.quantity for l in links.links_of(make("a", C.LIGHT_AUTOMATIC, SP)) if l.quantity == "intensity"])
        self.assertEqual([], links.links_of(make("b", C.LIGHT_NON_EXPORTING, PM)))
        self.assertEqual([], links.links_of(make("c", C.LIGHT_CUSTOM)))
        self.assertEqual([], links.links_of(make("d", C.LIGHT_NAMED, "pad_flood")))

    # ---- Reach and Custom Distance --------------------------------------------------------------------------
    def test_a_spills_reach_is_its_custom_distance(self) -> None:
        data = make("flood", C.LIGHT_SPILL_CUSTOM)
        data.xplane.size = 3.0
        self.assertTrue(data.use_custom_distance)
        self.assertAlmostEqual(3.0, data.cutoff_distance, places=5)
        settled(data)
        data.cutoff_distance = 7.5
        sync.blender_changed()
        self.assertAlmostEqual(7.5, data.xplane.size, places=5)

    def test_switching_the_custom_distance_on_takes_the_reach_it_has(self) -> None:
        data = make("flood", C.LIGHT_SPILL_CUSTOM)
        data.xplane.size = 2.0
        data.use_custom_distance = False
        settled(data)
        data.cutoff_distance = 40.0
        data.use_custom_distance = True
        sync.blender_changed()
        self.assertAlmostEqual(2.0, data.xplane.size, places=5)
        self.assertAlmostEqual(2.0, data.cutoff_distance, places=5)

    def test_a_library_spill_reaches_as_far_as_its_light_size(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, SP)
        data.xplane.param_size = 12.0
        self.assertAlmostEqual(12.0, data.cutoff_distance, places=5)
        settled(data)
        data.cutoff_distance = 30.0
        sync.blender_changed()
        self.assertAlmostEqual(30.0, data.xplane.param_size, places=5)

    def test_a_light_lit_by_intensity_has_no_reach_to_link(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.use_custom_distance = True
        data.cutoff_distance = 5.0
        settled(data)
        data.cutoff_distance = 9.0
        sync.blender_changed()
        self.assertEqual(1.0, data.xplane.param_size)

    def test_a_glow_sprites_size_is_not_a_reach(self) -> None:
        data = make("sprite", C.LIGHT_CUSTOM)
        data.xplane.size = 4.0
        self.assertFalse(data.use_custom_distance)

    # ---- typed lights -------------------------------------------------------------------------------------
    def test_the_color_of_a_typed_light_goes_both_ways(self) -> None:
        data = make("lamp", C.LIGHT_PARAM, PM, line(PM, INTENSITY=500.0, WIDTH=0.5))
        data.xplane.params += " // left"
        data.xplane_params.color = (0.2, 0.4, 0.6)
        self.assertEqual([0.2, 0.4, 0.6], [round(c, 4) for c in data.color])
        settled(data)
        data.color = (0.9, 0.8, 0.1)
        sync.blender_changed()
        words = data.xplane.params.split()
        self.assertEqual(["0.9", "0.8", "0.1"], words[:3])
        # Nothing else of the line was touched, the comment included
        self.assertEqual(["0", "500cd"], words[3:5])
        self.assertTrue(data.xplane.params.endswith("// left"))

    def test_the_cone_of_a_typed_light_is_an_angle_in_blender(self) -> None:
        data = make("lamp", C.LIGHT_PARAM, PM, line(PM, WIDTH=0.5))
        data.xplane_params.cone_angle = math.radians(90)
        self.assertAlmostEqual(math.cos(math.radians(45)), lp.values_of(data.xplane.params, ["R", "G", "B", "INDEX", "INTENSITY", "DX", "DY", "DZ", "WIDTH"])["WIDTH"], places=5)
        self.assertAlmostEqual(math.radians(90), data.spot_size, places=5)
        settled(data)
        data.spot_size = math.radians(40)
        sync.blender_changed()
        self.assertAlmostEqual(math.cos(math.radians(20)), links.Cone().stored(data), places=5)
        self.assertAlmostEqual(math.radians(40), data.xplane_params.cone_angle, places=5)

    def test_the_cone_of_an_older_light_also_turns_its_direction(self) -> None:
        formal = list(lights_txt.get_parsed_light(BILLBOARD).light_param_def)
        self.assertEqual("billboard", links.cone_style(BILLBOARD))
        width = links.width_of("billboard", math.radians(60))
        data = make("lamp", C.LIGHT_PARAM, BILLBOARD, line(BILLBOARD, WIDTH=width, DX=0.0, DY=-(1 - width), DZ=0.0))
        self.assertAlmostEqual(math.radians(60), links.spot_size_of("billboard", width), places=5)
        settled(data)
        data.spot_size = math.radians(90)
        sync.blender_changed()
        values = lp.values_of(data.xplane.params, formal)
        new_width = links.width_of("billboard", math.radians(90))
        self.assertAlmostEqual(new_width, values["WIDTH"], places=4)
        self.assertAlmostEqual(-(1 - new_width), values["DY"], places=4)
        self.assertAlmostEqual(0.0, values["DX"], places=5)

    def test_the_power_and_reach_of_a_typed_light_keep_their_units_and_other_words(self) -> None:
        data = make("lamp", C.LIGHT_PARAM, PM, line(PM, INTENSITY=1000.0, INDEX=3.0))
        data.energy = 100.0
        settled(data)
        data.energy = 500.0
        sync.blender_changed()
        words = data.xplane.params.split()
        self.assertTrue(words[4].endswith("cd"), words)
        self.assertEqual("3", words[3])
        self.assertAlmostEqual(500.0 / WATTS_PER_CANDELA, float(words[4][:-2]), delta=5.0)
        spill = make("spill", C.LIGHT_PARAM, SP, line(SP, SIZE=4.0))
        self.assertAlmostEqual(4.0, links.Reach().stored(spill), places=5)
        spill.xplane_params.size = 6.0
        self.assertAlmostEqual(6.0, spill.cutoff_distance, places=5)

    def test_editing_the_typed_text_changes_the_blender_light(self) -> None:
        data = make("lamp", C.LIGHT_PARAM, PM, line(PM))
        data.energy = 50.0
        data.xplane.params = line(PM, R=0.1, G=0.2, B=0.3, INTENSITY=2000.0, WIDTH=0.0)
        self.assertEqual([0.1, 0.2, 0.3], [round(c, 4) for c in data.color])
        self.assertAlmostEqual(2000.0 * WATTS_PER_CANDELA, data.energy, places=3)
        self.assertAlmostEqual(math.pi, data.spot_size, places=5)

    def test_a_typed_light_that_shines_all_around_has_no_cone_to_link(self) -> None:
        omni = make("omni", C.LIGHT_PARAM, PM, line(PM, WIDTH=1.0))
        self.assertNotIn("cone", [l.quantity for l in links.links_of(omni)])
        point = make("point", C.LIGHT_PARAM, PM, line(PM, WIDTH=0.5), type_="POINT")
        self.assertNotIn("cone", [l.quantity for l in links.links_of(point)])

    def test_colors_a_picker_cannot_hold_are_left_in_the_line(self) -> None:
        data = make("lamp", C.LIGHT_PARAM, PM, line(PM, R=3.0, G=1.0, B=1.0))
        data.color = (0.5, 0.5, 0.5)
        settled(data)
        data.xplane.params = line(PM, R=3.0, G=0.2, B=0.2)
        self.assertEqual([0.5, 0.5, 0.5], [round(c, 4) for c in data.color])

    def test_a_new_typed_light_takes_the_color_and_cone_of_the_blender_light(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, "", "")
        data.color = (0.2, 0.4, 0.6)
        data.spot_size = math.radians(60)
        data.xplane.type = C.LIGHT_PARAM
        bpy.ops.xplane.light_pick_name("EXEC_DEFAULT", light=PM)
        words = lp.values_of(data.xplane.params, list(lights_txt.get_parsed_light(PM).light_param_def))
        self.assertEqual([0.2, 0.4, 0.6], [round(words[c], 4) for c in "RGB"])
        self.assertAlmostEqual(math.cos(math.radians(30)), words["WIDTH"], places=5)
        # A direction too, or the cone would start with none: the Blender light shines down, which is X-Plane's -Y
        self.assertAlmostEqual(-1.0, words["DY"], places=5)
        self.assertAlmostEqual(0.0, words["DX"], places=5)

    # ---- nothing is moved when it must not be -------------------------------------------------------------
    def test_nothing_is_pushed_or_pulled_while_paused(self) -> None:
        data = make("lamp", C.LIGHT_AUTOMATIC, PM)
        data.energy = 300.0
        settled(data)
        with sync.paused():
            data.xplane.param_intensity_new = 99999.0
            data.energy = 1.0
            sync.blender_changed()
        self.assertAlmostEqual(1.0, data.energy)
        self.assertEqual(99999.0, data.xplane.param_intensity_new)

    def test_the_preview_leaves_both_sides_saying_the_same(self) -> None:
        obj = bpy.data.objects.new("lamp", make("lamp", C.LIGHT_AUTOMATIC, PM))
        bpy.context.scene.collection.objects.link(obj)
        obj.data.xplane.param_intensity_new = 30000.0
        from io_xplane2blender import xplane_light_tools

        self.assertTrue(xplane_light_tools.apply_preview(obj, 2.0))
        self.assertAlmostEqual(30000.0 * WATTS_PER_CANDELA * 2.0, obj.data.energy, places=2)
        self.assertEqual(2.0, obj.data[sync.STRENGTH])
        self.assertEqual(30000.0, obj.data.xplane.param_intensity_new)
        xplane_light_tools.apply_preview(obj, 1.0)
        self.assertNotIn(sync.STRENGTH, obj.data)

    def test_the_handler_is_registered_with_the_add_on(self) -> None:
        self.assertIn(sync.blender_changed, bpy.app.handlers.depsgraph_update_post)
        self.assertIn(sync.forget, bpy.app.handlers.load_post)


runTestCases([TestLightSync])
