"""
Round trips of what Laminar's own aircraft do, found by importing and exporting every OBJ of X-Plane 12's aircraft:
older files with animation after geometry, levers with detents, held keys and lift datarefs, tilted hinges
"""

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import TempFolder, obj_text, write_file, write_png
from io_xplane2blender.tests.obj_evaluator import corners, max_distance
from io_xplane2blender.tests.roundtrip_helpers import HOUSE_IDX, HOUSE_VT, test_values
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file
from io_xplane2blender.xplane_importer.obj_parser import parse_obj


def lines(text: str, *directives: str):
    """The lines of these directives, numbers rounded so that 0.020682 and 0.0207 compare"""

    def word(w):
        try:
            return str(round(float(w), 3) + 0.0)
        except ValueError:
            return w

    return [
        " ".join(word(w) for w in line.split())
        for line in text.splitlines()
        if line.split()[:1] and line.split()[0] in directives
    ]


class TestImportRoundTripLaminar(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        write_png(self.folder.join("tex.png"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def round_trip(self, body: str, header: str = "TEXTURE tex.png\n"):
        text = obj_text(body, header=header, vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        built = import_obj_file(write_file(self.folder.join("part.obj"), text), ImportOptions(make_exportable=True), ImportReport())
        built.collection.xplane.layer.name = self.folder.join("part")
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        original, again = parse_obj(text), parse_obj(exported)
        for values in test_values(original):
            with self.subTest(values=values):
                self.assertLess(max_distance(corners(original, values), corners(again, values)), 2e-3)
        return text, exported

    def test_a_reverse_lever_after_the_throttle_and_its_buttons(self) -> None:
        # The Citation X: the throttle rotates and lifts, then a nested block, then the reverse lever's animation in
        # the same block, which X-Plane applies to the reverse lever only
        self.round_trip(
            "ANIM_begin\nANIM_trans 0 0.3 2.7 0 0.3 2.7\n"
            "ANIM_rotate_begin -1 0 0 sim/throttle\nANIM_rotate_key -1 0\nANIM_rotate_key 0 10\nANIM_rotate_key 1 53\nANIM_rotate_end\n"
            "ANIM_trans 0 -0.3 -2.7 0 -0.3 -2.7\n"
            "ANIM_trans 0 0 0 0 0.007 0.007 0 1 sim/detent\n"
            "ATTR_manip_drag_rotate hand 0 0.3 2.7 -1 0 0 0 53 0.010056 -1 1 0 1 sim/throttle sim/detent Throttle\n"
            "ATTR_axis_detent_range -1 -1 0\nATTR_axis_detent_range -1 0 1\nATTR_axis_detent_range 0 0 0\n"
            "ATTR_axis_detent_range 0 1 0\nATTR_axis_detent_range 1 1 0\n"
            "TRIS 0 6\n"
            "ANIM_begin\nANIM_trans 0 0 0 0.0036 0 0 0 1 CMND=sim/toga\nATTR_manip_command button sim/toga Go Around\nTRIS 6 6\nANIM_end\n"
            "ANIM_trans 0 0.47 2.8 0 0.47 2.8\nANIM_rotate 1 0 0 90 0 -1 0 sim/reverse\nANIM_trans 0 -0.47 -2.8 0 -0.47 -2.8\n"
            "ATTR_manip_drag_rotate hand 0 0.47 2.8 1 0 0 90 0 0 -1 0 0 0 sim/reverse none Reverse\n"
            "TRIS 0 6\nANIM_end\n"
        )

    def test_a_lift_dataref_from_0_to_1(self) -> None:
        # The S-76's fuel levers: the lift is 7 mm, the detent dataref goes from 0 to 1 and the heights are in its units
        _, exported = self.round_trip(
            "ANIM_begin\nANIM_trans 0 1 2 0 1 2\n"
            "ANIM_rotate_begin 1 0 0 sim/fuel\nANIM_rotate_key 0 0\nANIM_rotate_key 1 12\nANIM_rotate_key 3 40\nANIM_rotate_end\n"
            "ANIM_trans 0 -1 -2 0 -1 -2\n"
            "ANIM_trans 0 0 0 0 -0.00748 0 0 1 sim/fuel_detent\n"
            "ATTR_manip_drag_rotate hand 0 1 2 1 0 0 0 40 0.00748 0 3 0 1 sim/fuel sim/fuel_detent FUEL\n"
            "ATTR_manip_keyframe 1 12\n"
            "ATTR_axis_detent_range 0 0.9 0\nATTR_axis_detent_range 0.9 1 1\nATTR_axis_detent_range 1 3 0\n"
            "TRIS 0 6\nANIM_end\n"
        )
        (line,) = lines(exported, "ATTR_manip_drag_rotate")
        # ATTR_manip_drag_rotate cursor x y z dx dy dz angle1 angle2 lift v1min v1max v2min v2max
        self.assertEqual(line.split()[11:15], ["0.0", "3.0", "0.0", "1.0"])
        self.assertEqual(["0.0 0.9 0.0", "0.9 1.0 1.0", "1.0 3.0 0.0"], [l[23:] for l in lines(exported, "ATTR_axis_detent_range")])

    def test_a_lever_held_at_one_end(self) -> None:
        # The MD-80's speedbrake is armed at -0.5 before it moves: its detents start there, so the drag does too
        _, exported = self.round_trip(
            "ANIM_begin\nANIM_trans 0 0.06 2.7 0 0.06 2.7\n"
            "ANIM_rotate_begin 1 0 0 sim/speedbrake\nANIM_rotate_key -0.5 0\nANIM_rotate_key 0 0\nANIM_rotate_key 1 45\nANIM_rotate_end\n"
            "ANIM_trans 0 -0.06 -2.7 0 -0.06 -2.7\n"
            "ANIM_begin\nANIM_trans 0 0 0 0 0.018 -0.009 0 1 sim/speedbrake_detent\n"
            "ATTR_manip_drag_rotate hand 0 0.06 2.7 1 0 0 0 45 0.0207 -0.5 1 0 1 sim/speedbrake sim/speedbrake_detent Speedbrakes\n"
            "ATTR_manip_keyframe 0 0\n"
            "ATTR_axis_detent_range -0.5 -0.5 1\nATTR_axis_detent_range -0.5 0 1\nATTR_axis_detent_range 0 0 0\n"
            "ATTR_axis_detent_range 0 1 0.3\n"
            "TRIS 0 6\nANIM_end\nANIM_end\n"
        )
        (line,) = lines(exported, "ATTR_manip_drag_rotate")
        self.assertEqual(line.split()[11:13], ["-0.5", "1.0"])
        self.assertEqual(["ATTR_manip_keyframe 0.0 0.0"], lines(exported, "ATTR_manip_keyframe"))

    def test_a_trim_wheel_with_a_stop_and_no_lift(self) -> None:
        # The C172's trim wheel has a detent line but no lift, which X-Plane reads as a stop
        _, exported = self.round_trip(
            "ANIM_begin\nANIM_trans -0.05 -0.2 0.3 -0.05 -0.2 0.3\n"
            "ANIM_rotate_begin 1 0 0 sim/trim\nANIM_rotate_key -1 -1440\nANIM_rotate_key 0 0\nANIM_rotate_key 1 1440\nANIM_rotate_end\n"
            "ANIM_trans 0.05 0.2 -0.3 0.05 0.2 -0.3\n"
            "ATTR_draw_disable\n"
            "ATTR_manip_drag_rotate hand -0.05 -0.2 0.3 1 0 0 -1440 1440 0 -1 1 0 0 sim/trim none Elevator trim\n"
            "ATTR_manip_keyframe 0 0\nATTR_axis_detent_range 0 0 0\nATTR_manip_wheel 0.005\n"
            "TRIS 0 6\nANIM_end\n"
        )
        self.assertEqual(["ATTR_axis_detent_range 0.0 0.0 0.0"], lines(exported, "ATTR_axis_detent_range"))

    def test_a_flap_lever_that_moves_unevenly(self) -> None:
        # The C172's flap handle: four keys along its drag, and a second direction to get past the detents
        _, exported = self.round_trip(
            "ANIM_begin\nANIM_trans_begin sim/flaps\nANIM_trans_key 0 0 0 0\nANIM_trans_key 0.333 0 -0.0149 0\n"
            "ANIM_trans_key 0.666 0 -0.0291 0\nANIM_trans_key 1 0 -0.0503 0\nANIM_trans_end\n"
            "ANIM_begin\nANIM_trans 0 0 0 0.004 0 0 0 1 sim/flap_shift\n"
            "ATTR_manip_drag_axis hand 0 -0.0503 0 0 1 sim/flaps Flaps\n"
            "ATTR_axis_detented 0.004 0 0 0 1 sim/flap_shift\n"
            "ATTR_axis_detent_range 0 0.333 0\nATTR_axis_detent_range 0.333 0.666 0.5\nATTR_axis_detent_range 0.666 1 1\n"
            "TRIS 0 6\nANIM_end\nANIM_end\n"
        )
        self.assertEqual(["ATTR_manip_drag_axis hand 0.0 -0.05 0.0 0.0 1.0 sim/flaps Flaps"], lines(exported, "ATTR_manip_drag_axis"))
        self.assertEqual(["ATTR_axis_detented 0.004 0.0 0.0 0.0 1.0 sim/flap_shift"], lines(exported, "ATTR_axis_detented"))
        self.assertEqual(3, len(lines(exported, "ATTR_axis_detent_range")))

    def test_a_tilted_hinge_stays_tilted(self) -> None:
        # The MD-82's wing tips flex about an axis 0.2 degrees off Z, nested five times: snapped to Z they were 10 cm off
        body = ""
        for x in (5, 8, 10, 12, 14):
            body += (
                f"ANIM_begin\nANIM_trans -{x} -1 24 -{x} -1 24\n"
                "ANIM_rotate_begin 0 0.0036 -0.99999 sim/flex\nANIM_rotate_key -20 -2\nANIM_rotate_key 20 4\nANIM_rotate_end\n"
                f"ANIM_trans {x} 1 -24 {x} 1 -24\n"
            )
        self.round_trip(body + "TRIS 0 12\n" + "ANIM_end\n" * 5)

    def test_a_drag_without_its_first_dataref(self) -> None:
        # The Baron's sun visors: "none" for dataref 1 must stay, or dataref 2 and the tooltip move into its place
        _, exported = self.round_trip("ATTR_manip_drag_xy hand 100 100 0 0 2 0 none sim/visor Sunvisor\nTRIS 0 6\n")
        self.assertEqual(
            ["ATTR_manip_drag_xy hand 100.0 100.0 0.0 0.0 2.0 0.0 none sim/visor Sunvisor"],
            lines(exported, "ATTR_manip_drag_xy"),
        )

    def test_magnets_with_spaces_in_their_names(self) -> None:
        _, exported = self.round_trip(
            "ATTR_manip_command button sim/x X\nTRIS 0 6\nATTR_manip_none\nMAGNET magnet pilot xpad 0 0 -0.15 0 170 0\n"
        )
        self.assertEqual(["MAGNET magnet pilot xpad 0.0 0.0 -0.15 0.0 170.0 0.0"], lines(exported, "MAGNET"))

    def test_culling_comes_back_on(self) -> None:
        # The C172's floats: two sided parts between culled ones
        text, exported = self.round_trip("TRIS 0 6\nATTR_no_cull\nTRIS 6 6\nATTR_cull\nATTR_shade_flat\nTRIS 0 6\n")

        def states(obj_text_):
            obj = parse_obj(obj_text_)
            return sorted((r.count, "cull" in dict(r.state), str(dict(r.state).get("shade"))) for r in obj.iter_tris())

        self.assertEqual(states(text), states(exported))

    def test_an_offset_ends(self) -> None:
        # The F-4's decals: offset parts, then ATTR_poly_os 0 for the rest
        text, exported = self.round_trip("ATTR_poly_os 2\nTRIS 0 6\nATTR_poly_os 0\nTRIS 6 6\n")

        def offsets(obj_text_):
            return sorted((r.offset > 0, str(dict(r.state).get("poly_os"))) for r in parse_obj(obj_text_).iter_tris())

        self.assertEqual([(False, "('2',)"), (True, "None")], offsets(text))
        self.assertEqual(sorted(dict(offsets(text)).values()), sorted(dict(offsets(exported)).values()))

    def test_a_screen_without_a_lighting_channel(self) -> None:
        # Laminar's G1000 screens: lighting channel -1
        _, exported = self.round_trip("ATTR_cockpit_device G1000_MFD 1 -1 1\nTRIS 0 6\n")
        self.assertEqual(["ATTR_cockpit_device G1000_MFD 1.0 -1.0 1.0"], lines(exported, "ATTR_cockpit_device"))

    def test_textures_keep_their_names(self) -> None:
        # X-Plane loads tex.dds for tex.png, and a normal map that is not shipped is still named
        write_png(self.folder.join("paint.dds"))
        _, exported = self.round_trip("TRIS 0 6\n", header="TEXTURE paint.png\nTEXTURE_NORMAL paint_NRM.png\n")
        self.assertEqual(["TEXTURE paint.png", "TEXTURE_NORMAL paint_NRM.png"], lines(exported, "TEXTURE", "TEXTURE_NORMAL"))


runTestCases([TestImportRoundTripLaminar])
