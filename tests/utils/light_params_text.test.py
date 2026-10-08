"""
Changing single values of the line of parameters of a hand-typed light
"""

from io_xplane2blender.tests import *
from io_xplane2blender.xplane_utils import xplane_light_params as lp

LANDING = ["R", "G", "B", "INDEX", "INTENSITY", "DX", "DY", "DZ", "WIDTH"]


class TestLightParamsText(XPlaneTestCase):
    def test_values_are_read_by_name(self) -> None:
        values = lp.values_of("1 0.5 0.25 3 20000cd 0 0 -1 0.9", LANDING)
        self.assertEqual({"R": 1.0, "G": 0.5, "B": 0.25, "INDEX": 3.0, "INTENSITY": 20000.0, "DX": 0.0, "DY": 0.0, "DZ": -1.0, "WIDTH": 0.9}, values)

    def test_a_missing_value_starts_with_its_default(self) -> None:
        values = lp.values_of("0.2 0.4", LANDING)
        self.assertEqual(0.2, values["R"])
        self.assertEqual(1.0, values["B"])
        self.assertEqual(20000.0, values["INTENSITY"])
        self.assertEqual(1.0, values["WIDTH"])

    def test_one_value_changes_and_the_rest_stays_as_typed(self) -> None:
        line = "1.0 0.50 0.25 3 20000cd 0 0 -1 0.9"
        self.assertEqual("1.0 0.50 0.25 3 20000cd 0 0 -1 0.8", lp.update_line(line, LANDING, {"WIDTH": 0.8}))

    def test_a_value_that_is_the_same_keeps_how_it_was_typed(self) -> None:
        line = "1.0 0.50 0.25 3 20000cd 0 0 -1 0.9"
        # The settings hold single precision numbers, so 0.9 comes back as 0.8999999761581421
        self.assertEqual(line, lp.update_line(line, LANDING, {"R": 1.0, "G": 0.5, "WIDTH": 0.8999999761581421}))

    def test_the_comment_is_kept(self) -> None:
        line = "1 1 1 0 500cd 0 0 -1 0.5 // left wing"
        self.assertEqual("1 1 1 0 800cd 0 0 -1 0.5 // left wing", lp.update_line(line, LANDING, {"INTENSITY": 800.0}))

    def test_the_unit_follows_the_value_it_replaces(self) -> None:
        self.assertEqual("1 1 1 0 800 0 0 -1 0.5", lp.update_line("1 1 1 0 500 0 0 -1 0.5", LANDING, {"INTENSITY": 800.0}))

    def test_a_short_line_is_filled_up_before_the_change(self) -> None:
        self.assertEqual("0.3 1 1 0 20000cd 0 0 0 1", lp.update_line("", LANDING, {"R": 0.3}))
        self.assertEqual("1 1 1 0 20000cd 0 0 0 0.5", lp.update_line("1 1 1", LANDING, {"WIDTH": 0.5}))

    def test_fixed_parameters_start_with_their_fixed_value(self) -> None:
        formal = ["ZERO", "ZERO_", "NEG_ONE", "INDEX", "SIZE"]
        self.assertEqual("0 0 -1 0 1", lp.default_line(formal))
        self.assertEqual("0 0 -1 2 1", lp.update_line("", formal, {"INDEX": 2.0}))
        self.assertTrue(lp.is_fixed("ZERO__"))
        self.assertFalse(lp.is_fixed("SIZE"))

    def test_the_comment_comes_after_exactly_the_wanted_number_of_values(self) -> None:
        self.assertEqual((["1", "2"], "three"), lp.split_line("1 2 three", 2))
        self.assertEqual((["1", "2"], ""), lp.split_line("1 2", 3))
        self.assertEqual(([], ""), lp.split_line("   ", 3))

    def test_numbers_are_read_like_the_exporter_reads_them(self) -> None:
        self.assertEqual(500.0, lp.number("500cd"))
        self.assertEqual(0.5, lp.number("0,5"))
        self.assertEqual(0.0, lp.number("text"))


runTestCases([TestLightParamsText])
