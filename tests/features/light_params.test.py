"""
A library light's typed parameters as settings: a color, a direction, a size. Each reads and writes the light's own
line of parameters, which stays what the exporter writes
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout
from io_xplane2blender.ui import light_card, light_params
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as lights_txt

LANDING = "airplane_landing_bb"  # R G B INDEX INTENSITY DX DY DZ WIDTH
FIXED_SHAPE = ["ZERO", "ZERO_", "NEG_ONE", "INDEX", "SIZE"]


def lamp(name: str = LANDING, params: str = "1 1 1 0 20000cd 0 0 -1 0.9") -> bpy.types.Light:
    data = bpy.data.lights.new("lamp", "SPOT")
    data.xplane.type = C.LIGHT_PARAM
    data.xplane.name = name
    data.xplane.params = params
    obj = bpy.data.objects.new("lamp", data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    return data


class TestLightParams(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()

    def test_the_settings_read_the_line(self) -> None:
        typed = lamp(params="0.5 0.25 0.125 3 800cd 0 -1 0 0.75").xplane_params
        self.assertEqual([0.5, 0.25, 0.125], [round(c, 4) for c in typed.color])
        self.assertEqual([0.0, -1.0, 0.0], list(typed.direction))
        self.assertEqual(3, typed.index)
        self.assertEqual(800.0, typed.intensity)
        self.assertAlmostEqual(0.75, typed.width, places=5)

    def test_changing_a_setting_changes_only_its_value_in_the_line(self) -> None:
        data = lamp(params="1.0 0.50 0.25 3 20000cd 0 0 -1 0.9 // left")
        data.xplane_params.intensity = 800
        self.assertEqual("1.0 0.50 0.25 3 800cd 0 0 -1 0.9 // left", data.xplane.params)
        data.xplane_params.color = (0.1, 0.2, 0.3)
        self.assertEqual("0.1 0.2 0.3 3 800cd 0 0 -1 0.9 // left", data.xplane.params)
        data.xplane_params.direction = (0.0, -0.5, -0.5)
        data.xplane_params.index = 7
        self.assertEqual("0.1 0.2 0.3 7 800cd 0 -0.5 -0.5 0.9 // left", data.xplane.params)

    def test_changing_one_color_channel_keeps_the_other_text(self) -> None:
        data = lamp(params="1.0 0.50 0.25 3 20000cd 0 0 -1 0.9")
        # What the color button sends when only the green channel moves: the others come back as single precision
        r, g, b = data.xplane_params.color
        data.xplane_params.color = (r, 0.75, b)
        self.assertEqual("1.0 0.75 0.25 3 20000cd 0 0 -1 0.9", data.xplane.params)

    def test_an_empty_line_is_filled_in_with_the_first_change(self) -> None:
        data = lamp(params="")
        data.xplane_params.width = 0.5
        self.assertEqual("1 1 1 0 20000cd 0 0 0 0.5", data.xplane.params)

    def test_editing_the_text_shows_in_the_settings(self) -> None:
        data = lamp()
        data.xplane.params = "0 0 1 0 5cd 0 0 -1 0.1"
        self.assertEqual([0.0, 0.0, 1.0], list(data.xplane_params.color))
        self.assertEqual(5.0, data.xplane_params.intensity)

    def test_fixed_parameters_are_never_settings(self) -> None:
        name = next(n for n, p in lights_txt._parsed_lights_txt_content.items() if list(p.light_param_def) == FIXED_SHAPE)
        data = lamp(name, "")
        data.xplane_params.size = 2.5
        self.assertEqual("0 0 -1 0 2.5", data.xplane.params)
        layout = FakeLayout()
        light_params.parameters_layout(layout, data)
        self.assertEqual(["size", "params"], [p for p in layout.props() if p in ("size", "params", "color")])

    def test_a_light_that_is_not_in_lights_txt_has_nothing_to_change(self) -> None:
        data = lamp("not_a_light", "1 2 3")
        data.xplane_params.width = 0.5
        self.assertEqual("1 2 3", data.xplane.params)
        self.assertEqual(0.0, data.xplane_params.width)
        layout = FakeLayout()
        light_params.parameters_layout(layout, data)
        self.assertEqual(["params"], layout.props())

    def test_the_card_shows_a_setting_for_each_parameter_and_the_text(self) -> None:
        data = lamp()
        layout = FakeLayout()
        light_params.parameters_layout(layout, data)
        self.assertEqual(["color", "index", "intensity", "direction", "width", "params"], layout.props())

    def test_every_library_light_with_parameters_draws(self) -> None:
        count = 0
        for name, parsed in lights_txt._parsed_lights_txt_content.items():
            if not parsed.light_param_def:
                continue
            data = lamp(name, "")
            light_params.parameters_layout(FakeLayout(), data)
            for single in light_params.SINGLES.values():
                getattr(data.xplane_params, single)
            count += 1
        self.assertGreater(count, 50)

    def test_picking_another_light_starts_its_parameters_again(self) -> None:
        data = lamp(params="1 2 3")
        bpy.ops.xplane.light_pick_name("EXEC_DEFAULT", light=LANDING)
        self.assertEqual("1 1 1 0 20000cd 0 0 0 1", data.xplane.params)
        # Parameters that fit are kept
        data.xplane.params = "0.3 0.3 0.3 1 500cd 0 0 -1 0.5"
        bpy.ops.xplane.light_pick_name("EXEC_DEFAULT", light="airplane_taxi_bb")
        self.assertEqual("0.3 0.3 0.3 1 500cd 0 0 -1 0.5", data.xplane.params)

    def test_picking_a_light_leaves_other_kinds_of_light_alone(self) -> None:
        data = lamp(params="")
        data.xplane.type = C.LIGHT_AUTOMATIC
        bpy.ops.xplane.light_pick_name("EXEC_DEFAULT", light=LANDING)
        self.assertEqual("", data.xplane.params)

    def test_the_light_card_draws_the_settings(self) -> None:
        from io_xplane2blender.tests.fake_layout import draw_panel

        lamp()
        layout = draw_panel(light_card.XPLANE_PT_light)
        self.assertIn("XPlaneLightParams.color", layout.settings())
        self.assertIn("XPlaneLightParams.direction", layout.settings())


runTestCases([TestLightParams])
