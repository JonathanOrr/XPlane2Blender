import itertools
import os

import bpy
from mathutils import Vector
from io_xplane2blender import xplane_constants
from io_xplane2blender.tests import *
from io_xplane2blender.xplane_helpers import unfinished
from io_xplane2blender.tests.importer_helpers import (
    TempFolder,
    obj_text,
    write_file,
    write_png,
)
from io_xplane2blender.tests.obj_evaluator import corners, max_distance
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file
from io_xplane2blender.xplane_importer.obj_parser import AnimNode, Light, parse_obj

# A little house shape: a floor quad and a wall quad, so that every transform is visible in the corners
HOUSE_VT = (
    "VT 0 0 0 0 1 0 0 0\nVT 0 0 -1 0 1 0 0 1\nVT 1 0 -1 0 1 0 1 1\nVT 1 0 0 0 1 0 1 0\n"
    "VT 0 0 0 0 0 1 0 0\nVT 1 0 0 0 0 1 1 0\nVT 1 1 0 0 0 1 1 1\nVT 0 1 0 0 0 1 0 1\n"
)
HOUSE_IDX = "IDX10 0 1 2 0 2 3\nIDX10 4 5 6 4 6 7\n"


def all_datarefs(obj):
    keys = {}

    def visit(node):
        for op in node.ops:
            if not op.is_static:
                keys.setdefault(op.dataref, set()).update(k[0] for k in op.keys)
        for line in node.visibility:
            keys.setdefault(line.dataref, set()).update((line.v1, line.v2))
        for child in node.children:
            if isinstance(child, AnimNode):
                visit(child)

    visit(obj.root)
    return keys


def test_values(obj):
    """Several settings of the datarefs: every key, and between keys"""
    datarefs = all_datarefs(obj)
    sets = []
    for choice in range(4):
        values = {}
        for path, keys in datarefs.items():
            ordered = sorted(keys)
            if choice == 0:
                values[path] = 0.0
            elif choice == 1:
                values[path] = ordered[-1]
            elif choice == 2:
                values[path] = ordered[0]
            else:
                values[path] = (ordered[0] + ordered[-1]) / 2 + 0.123 * (ordered[-1] - ordered[0])
        sets.append(values)
    return sets


def light_summaries(text):
    """Every light as (kind, name, parameters, position), numbers rounded, ignoring where in the blocks it sits"""
    found = []

    def number(value):
        try:
            return round(float(value), 4)
        except ValueError:
            return value

    def visit(node):
        for child in node.children:
            if isinstance(child, AnimNode):
                visit(child)
            elif isinstance(child, Light):
                found.append(
                    (
                        child.kind,
                        child.name,
                        tuple(number(a) for a in child.args),
                        tuple(round(v, 4) for v in child.position),
                    )
                )

    visit(parse_obj(text).root)
    return sorted(found, key=repr)


class TestImportRoundTrip(XPlaneTestCase):
    """Imports an OBJ, exports it with XPlane2Blender, and checks both look identical to X-Plane"""

    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        write_png(self.folder.join("tex.png"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def assert_round_trip(self, body: str, header: str = "TEXTURE tex.png\n") -> None:
        text = obj_text(body, header=header, vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        report = ImportReport()
        built = import_obj_file(path, ImportOptions(make_exportable=True), report)
        self.assertIsNotNone(built, report.errors)
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        original = parse_obj(text)
        again = parse_obj(exported)
        for values in test_values(original):
            with self.subTest(values=values):
                expected = corners(original, values)
                actual = corners(again, values)
                self.assertEqual(expected.shape, actual.shape)
                self.assertLess(max_distance(expected, actual), 2e-3)

    def assert_lights_round_trip(self, body: str) -> None:
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris="TRIS 0 6\n")
        path = write_file(self.folder.join("lights.obj"), text)
        built = import_obj_file(path, ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        self.assertEqual(light_summaries(text), light_summaries(exported))

    def test_named_and_param_lights(self) -> None:
        # The parameters are written back as they were: a spill (_pm) with a cone, and its billboard
        self.assert_lights_round_trip(
            "LIGHT_NAMED ship_mast_powered 1 2 3\n"
            "LIGHT_PARAM airplane_generic_pm 0.5 1 -2 1 0.5 0 18 25cd 0 -1 0 0.5\n"
            "LIGHT_PARAM airplane_generic_bb 0.5 1 -2 1 0.5 0 18 25cd 0 -1 0 0.5\n"
        )

    def test_custom_lights_keep_alpha_size_texture_and_odd_colors(self) -> None:
        # The power is the alpha, and a halo may hold placeholder colors the color picker can not
        self.assert_lights_round_trip(
            "LIGHT_CUSTOM 1 2 3 1 0.5 0.25 0.75 2.5 0.1 0.2 0.3 0.4 sim/graphics/animation/lights/airplane_generic_light\n"
            "LIGHT_CUSTOM -1 0 0.5 -1 0 -0.5 -2 3 0.5 0.5 1 1 sim/graphics/animation/lights/airplane_navigation_light_dir\n"
        )

    def test_custom_spill_lights(self) -> None:
        # Omni, and with a cone pointing down and sideways
        self.assert_lights_round_trip(
            "LIGHT_SPILL_CUSTOM 1 2 3 1 0.5 0.25 1 0.4 0 0 0 1 my/dataref\n"
            "LIGHT_SPILL_CUSTOM 0.5 1 -2 0.9 0.8 0.7 1 0.15 0 -1 0 0.6 my/other\n"
            "LIGHT_SPILL_CUSTOM -1 1 0 0.9 0.8 0.7 1 0.15 0.6 -0.8 0 0.75 none\n"
        )

    def test_x_plane_9_lights(self) -> None:
        # X-Plane 12 has no equivalent of the old VLIGHT lights: they come in keeping their color,
        # wait for an X-Plane 12 light to be picked, and are left out of exports until then
        vertices = HOUSE_VT + "VLIGHT 1 2 3 1 0.5 0\nVLIGHT 0 1 0 9.9 9.9 9.9\nVLIGHT 0 0 1 -1 0 0.25\n"
        text = obj_text("LIGHTS 0 3\n", header="TEXTURE tex.png\n", vertices=vertices, indices=HOUSE_IDX, tris="TRIS 0 6\n")
        path = write_file(self.folder.join("old_lights.obj"), text)
        built = import_obj_file(path, ImportOptions(make_exportable=True), ImportReport())
        lights = [o.data for o in built.collection.all_objects if o.type == "LIGHT"]
        self.assertEqual(3, len(lights))
        for light in lights:
            self.assertEqual(xplane_constants.LIGHT_AUTOMATIC, light.xplane.type)
            self.assertEqual("", light.xplane.name)
        self.assertIn((1.0, 0.5, 0.0), [tuple(round(c, 3) for c in light.color) for light in lights])
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        self.assertEqual([], light_summaries(exported))
        self.assertEqual(3, len(unfinished.items["lights without an X-Plane light chosen"]))

    def test_lights_in_moving_parts_keep_their_direction(self) -> None:
        # A static rotation around a spill light is folded into its position, the cone must still point the same way
        text = obj_text(
            "ANIM_begin\nANIM_trans 1 1 0 1 1 0\nANIM_rotate 0 0 1 30 30\n"
            "LIGHT_PARAM airplane_generic_pm 0.5 1 -2 1 0.5 0 18 25cd 0 -1 0 0.5\nANIM_end\n",
            header="TEXTURE tex.png\n",
            vertices=HOUSE_VT,
            indices=HOUSE_IDX,
            tris="TRIS 0 6\n",
        )
        path = write_file(self.folder.join("lights.obj"), text)
        built = import_obj_file(path, ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        again = import_obj_file(write_file(self.folder.join("again.obj"), exported), ImportOptions(), ImportReport())
        bpy.context.view_layer.update()

        def frames(result):
            (light,) = [o for o in result.objects if o.type == "LIGHT"]
            return light.matrix_world.translation, light.matrix_world.to_3x3() @ Vector((0, 0, -1))

        (position1, direction1), (position2, direction2) = frames(built), frames(again)
        self.assertLess((position1 - position2).length, 1e-4)
        self.assertLess((direction1 - direction2).length, 1e-4)

    def test_nothing_animated(self) -> None:
        self.assert_round_trip("TRIS 0 6\nTRIS 6 6\n")

    def test_static_transforms(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 2 1 -3 2 1 -3\nANIM_rotate 0 1 0 30 30\nANIM_rotate 1 0 0 -20 -20\n"
            "TRIS 0 6\nANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_rotate 0 0 1 15 15\nTRIS 6 6\nANIM_end\nANIM_end\n"
        )

    def test_rotation_about_a_principal_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 2 3 1 2 3\nANIM_rotate_begin 0 1 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_rotation_about_the_negative_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_rotate_begin 0 0 -1 sim/rot\nANIM_rotate_key -10 -45\nANIM_rotate_key 10 45\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_rotation_with_several_keys(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_rotate_begin 1 0 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 0.5 60\nANIM_rotate_key 1 30\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_translation(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans_begin sim/slide\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0.5 1 2\nANIM_trans_end\n"
            "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_rotation_about_an_arbitrary_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_rotate_begin 1 1 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 1 70\n"
            "ANIM_rotate_end\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_nested_animations(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 1 -2 0 1 -2\nANIM_rotate_begin 0 1 0 sim/outer\nANIM_rotate_key 0 0\nANIM_rotate_key 1 40\nANIM_rotate_end\n"
            "TRIS 0 6\n"
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_rotate_begin 1 0 0 sim/inner\nANIM_rotate_key 0 0\nANIM_rotate_key 1 -60\nANIM_rotate_end\n"
            "TRIS 6 6\nANIM_end\nANIM_end\n"
        )

    def test_rotate_then_translate_in_one_block(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_rotate_begin 0 0 1 sim/spin\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\n"
            "ANIM_trans_begin sim/push\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 1 0 0\nANIM_trans_end\n"
            "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_two_animated_meshes_share_nothing(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_rotate_begin 0 1 0 sim/a\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nTRIS 0 6\nANIM_end\n"
            "ANIM_begin\nANIM_trans_begin sim/b\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0 2 0\nANIM_trans_end\nTRIS 6 6\nANIM_end\n"
        )

    def test_show_and_hide_survive(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_show 0.5 1.5 sim/vis\nTRIS 0 6\nANIM_end\nANIM_begin\nANIM_hide 0.5 1.5 sim/vis\nTRIS 6 6\nANIM_end\n"
        )

    # The parts carry their own animations, in a frame where a static turn comes first, and one object does
    # what one dataref does to a part. All of it must still be the same for X-Plane
    @staticmethod
    def rotate(axis: str, dataref: str, keys=((0, 0), (1, 70))) -> str:
        lines = "".join(f"ANIM_rotate_key {v} {a}\n" for v, a in keys)
        return f"ANIM_rotate_begin {axis} {dataref}\n{lines}ANIM_rotate_end\n"

    @staticmethod
    def translate(dataref: str, keys=((0, (0, 0, 0)), (1, (0.5, 1, 2)))) -> str:
        lines = "".join(f"ANIM_trans_key {v} {x} {y} {z}\n" for v, (x, y, z) in keys)
        return f"ANIM_trans_begin {dataref}\n{lines}ANIM_trans_end\n"

    def test_a_static_turn_then_a_rotation(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 2 -1 1 2 -1\nANIM_rotate 0 1 0 30 30\nANIM_rotate 1 0 0 -20 -20\n"
            + self.rotate("0 0 1", "sim/a")
            + "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_a_static_turn_then_a_rotation_about_an_arbitrary_axis(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 2 -1 1 2 -1\nANIM_rotate 0 1 0 30 30\n"
            + self.rotate("1 1 0", "sim/a")
            + "TRIS 0 6\nANIM_end\n"
        )

    def test_a_static_turn_then_a_translation(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 2 -1 1 2 -1\nANIM_rotate 0 1 0 30 30\nANIM_rotate 1 0 0 -20 -20\n"
            + self.translate("sim/a")
            + "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_parts_in_one_frame(self) -> None:
        part = "ANIM_begin\nANIM_trans %s 0 -1 %s 0 -1\nANIM_rotate 0 1 0 45 45\n" + "%s" + "TRIS %s 6\nANIM_end\n"
        self.assert_round_trip(
            part % (1, 1, self.translate("sim/a"), 0) + part % (2, 2, self.rotate("0 0 1", "sim/b"), 6)
        )

    def test_a_move_and_a_turn_of_one_dataref_are_one_object(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 0 -1 1 0 -1\n"
            + self.translate("sim/a")
            + self.rotate("0 1 0", "sim/a", ((0, 0), (0.5, 20), (1, 70)))
            + "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_a_move_and_a_turn_of_one_dataref_with_different_keys(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\n"
            + self.translate("sim/a", ((0, (0, 0, 0)), (0.3, (1, 0, 0)), (1, (1, 1, 0))))
            + self.rotate("0 0 1", "sim/a", ((-1, -50), (0.6, 20), (1, 70)))
            + "TRIS 0 6\nANIM_end\n"
        )

    def test_a_move_and_a_turn_of_two_datarefs(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\n" + self.translate("sim/a") + self.rotate("0 1 0", "sim/b") + "TRIS 0 6\nANIM_end\n"
        )

    def test_turns_about_three_axes_of_one_dataref(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\n"
            + self.rotate("0 1 0", "sim/a", ((0, 0), (1, 40)))
            + self.rotate("1 0 0", "sim/a", ((0, 0), (1, 30)))
            + self.rotate("0 0 1", "sim/a", ((0, 0), (1, -25)))
            + "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_turns_about_two_axes_of_one_dataref_in_nested_blocks(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\n" + self.rotate("0 0 1", "sim/a") + "ANIM_begin\n" + self.rotate("1 0 0", "sim/a", ((0, 0), (1, -35)))
            + "TRIS 0 6\nANIM_end\nANIM_end\n"
        )

    def test_two_turns_about_the_same_axis_and_dataref(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\n" + self.rotate("0 1 0", "sim/a") + self.rotate("0 1 0", "sim/a", ((0, 0), (1, 10))) + "TRIS 0 6\nANIM_end\n"
        )

    def test_a_turn_about_another_pivot_of_the_same_dataref(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\n" + self.rotate("0 1 0", "sim/a") + "ANIM_trans 1 0 0 1 0 0\n" + self.rotate("0 0 1", "sim/a", ((0, 0), (1, 45)))
            + "TRIS 0 6\nANIM_end\n"
        )

    def test_a_part_with_something_static_after_its_animation(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\n" + self.rotate("0 1 0", "sim/a") + "ANIM_trans 1 0 -1 1 0 -1\nANIM_rotate 0 0 1 20 20\nTRIS 0 6\nANIM_end\n"
        )
        self.assert_round_trip(
            "ANIM_begin\n" + self.translate("sim/a") + "ANIM_trans 1 0 -1 1 0 -1\nANIM_rotate 0 0 1 20 20\nTRIS 0 6\nANIM_end\n"
        )

    def test_show_and_hide_on_a_part_that_moves(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_show 0.5 1.5 sim/vis\n"
            + self.rotate("0 1 0", "sim/a")
            + "TRIS 0 6\nANIM_end\n"
        )

    def test_show_and_hide_in_a_frame(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_rotate 0 0 1 90 90\nANIM_hide 0.5 1.5 sim/vis\nTRIS 0 6\nANIM_end\n"
        )

    def test_a_gear_leg_turns_down_and_back(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 -2.3596799 6.5805802 0 -2.3596799 6.5805802\nANIM_rotate 0 0 -1 90.00021 90.00021\n"
            "ANIM_rotate 1 0 0 90.00021 90.00021\n"
            "ANIM_rotate_begin 0 0 -1 sim/gear[0]\nANIM_rotate_key 1 -0\nANIM_rotate_key 0.9 -0\nANIM_rotate_key 0.1 112.99988\nANIM_rotate_key 0 112.99988\nANIM_rotate_end\n"
            "TRIS 0 6\nTRIS 6 6\nANIM_end\n"
        )

    def test_a_throttle_with_a_hidden_part_and_another_part(self) -> None:
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 1 -2 0 1 -2\nANIM_rotate 1 0 0 90 90\n"
            + self.rotate("1 0 0", "sim/d", ((-1, 0), (0, 0), (1, -54)))
            + "ANIM_begin\nANIM_hide -1 -0.0001 sim/d\nTRIS 0 6\nANIM_end\n"
            + "ANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_rotate 0 1 0 90 90\nTRIS 6 6\nANIM_end\n"
            + "ANIM_end\n"
        )

    def test_parts_hidden_by_default_under_a_rotation(self) -> None:
        # The importer marks what X-Plane hides with the datarefs at their defaults (nav_pos 0): they are exported,
        # where they are when the wing flexes
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 3 0 1 3 0 1\n"
            + self.rotate("0 0 -1", "sim/flex", ((-7, 0), (7, -3)))
            + "ANIM_begin\nANIM_hide -0.5 1.5 sim/nav_pos\nATTR_light_level 0 1 sim/off 0\nTRIS 0 6\nANIM_end\n"
            + "ANIM_begin\nANIM_hide -0.5 1.5 sim/nav_pos\nATTR_light_level 0 1 sim/nav 7500\nTRIS 6 6\nANIM_end\n"
            + "ANIM_begin\nANIM_hide 1.5 2.5 sim/nav_pos\nTRIS 0 6\nANIM_end\n"
            + "ANIM_end\n"
        )

    def test_light_level_brightness(self) -> None:
        text = obj_text("ATTR_light_level 0 1 sim/nav 7500\nTRIS 0 6\n", header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        built = import_obj_file(write_file(self.folder.join("lit.obj"), text), ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        lines = [line.split() for line in exported.splitlines() if line.strip().startswith("ATTR_light_level\t") or line.strip().startswith("ATTR_light_level ")]
        self.assertEqual([["ATTR_light_level", "0", "1", "sim/nav", "7500"]], lines)

    def test_parts_with_different_materials_keep_them(self) -> None:
        # Three screens in one place differ only by device: each keeps its own (the exporter reads one material per mesh)
        body = (
            "ATTR_cockpit_device MCDU_1 8 6 1\nTRIS 0 6\n"
            "ATTR_cockpit_device MCDU_2 4 7 1\nTRIS 6 6\n"
            "ATTR_cockpit_device MCDU_3 8 8 1\nTRIS 0 6\n"
        )
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        built = import_obj_file(write_file(self.folder.join("fms.obj"), text), ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        devices = sorted(" ".join(line.split()[1:]) for line in exported.splitlines() if line.split()[:1] == ["ATTR_cockpit_device"])
        self.assertEqual(["MCDU_1 8 6 1", "MCDU_2 4 7 1", "MCDU_3 8 8 1"], devices)

    def test_hud_glass_and_lit_only_end_where_they_ended(self) -> None:
        body = (
            "ATTR_hud_glass\nATTR_cockpit_lit_only 500\nTRIS 6 6\n"
            "ATTR_hud_reset\nATTR_no_cockpit\nTRIS 0 6\n"
        )
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        built = import_obj_file(write_file(self.folder.join("hud.obj"), text), ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)

        def states(obj_text_):
            obj = parse_obj(obj_text_)
            found = {}
            for run in obj.iter_tris():
                corners_ = obj.vertices[obj.indices[run.offset:run.offset + run.count], :3].round(3)
                state = dict(run.state)
                found[tuple(sorted(map(tuple, corners_.tolist())))] = ("hud_glass" in state, "cockpit_lit_only" in state)
            return found

        self.assertEqual(states(text), states(exported))

    def test_a_knob_with_two_parts_that_show_and_hide(self) -> None:
        # Hiding a part must not hide the ones beside it, which one of them carrying the animation would do
        self.assert_round_trip(
            "ANIM_begin\nANIM_trans 0 1 -2 0 1 -2\n"
            + self.rotate("0 1 0", "sim/push", ((-1, -20), (0, 0), (1, 30)))
            + "ANIM_begin\nANIM_hide 0 0.5 sim/mode\nANIM_trans 2 0 0 2 0 0\nTRIS 0 6\nANIM_end\n"
            + "TRIS 6 6\n"
            + "ANIM_begin\nANIM_hide 0.5 1 sim/mode\nANIM_trans 0 3 0 0 3 0\nTRIS 0 6\nTRIS 6 6\nANIM_end\n"
            + "ANIM_end\n"
        )

    def drag_rotate_lines(self, body: str):
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        built = import_obj_file(write_file(self.folder.join("part.obj"), text), ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        return built, [line.split() for line in exported.splitlines() if line.split()[:1] in (["ATTR_manip_drag_rotate"], ["ATTR_axis_detent_range"])]

    def test_a_drag_rotate_without_a_second_dataref_keeps_its_none(self) -> None:
        body = (
            "ANIM_begin\nANIM_trans 0 1 0 0 1 0\n"
            + self.rotate("0 0 1", "sim/r", ((0, 0), (1, 90)))
            + "ATTR_manip_drag_rotate hand 0 1 0 0 0 1 0 90 0 0 1 0 0 sim/r none Turn\nTRIS 0 6\nANIM_end\n"
        )
        built, lines = self.drag_rotate_lines(body)
        (line,) = lines
        self.assertEqual(["sim/r", "none", "Turn"], line[-3:])

    def test_a_drag_rotate_with_detents_is_the_detent_type_and_exports_again(self) -> None:
        body = (
            "ANIM_begin\nANIM_trans 0 1 0 0 1 0\n"
            + self.rotate("0 0 1", "sim/r", ((0, 0), (1, 90)))
            + "ANIM_begin\nANIM_trans_begin sim/lift\nANIM_trans_key 0 0 0 0\nANIM_trans_key 0.01 0 0 -0.01\nANIM_trans_end\n"
            + "ATTR_manip_drag_rotate hand 0 1 0 0 0 1 0 90 0.01 0 1 0 0.01 sim/r sim/lift Flap\n"
            + "ATTR_axis_detent_range 0 0 0\nATTR_axis_detent_range 0 0.5 0.01\nATTR_axis_detent_range 0.5 1 0.01\nTRIS 0 6\nANIM_end\nANIM_end\n"
        )
        built, lines = self.drag_rotate_lines(body)
        (manip,) = [m for m in built.objects if m.xplane.manip.enabled]
        self.assertEqual(xplane_constants.MANIP_DRAG_ROTATE_DETENT, manip.xplane.manip.type)
        self.assertEqual(["sim/r", "sim/lift", "Flap"], lines[0][-3:])
        self.assertEqual(4, len(lines))  # the manipulator and its three detent ranges

    def test_lods_survive(self) -> None:
        body = "ATTR_LOD 0 500\nTRIS 0 6\nATTR_LOD 500 2000\nTRIS 6 6\n"
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        built = import_obj_file(path, ImportOptions(all_lods=True, make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lods = [line.split() for line in exported.splitlines() if line.startswith("ATTR_LOD")]
        self.assertEqual(lods, [["ATTR_LOD", "0", "500"], ["ATTR_LOD", "500", "2000"]])
        again = parse_obj(exported)
        self.assertEqual([r.lod for r in again.iter_tris()], [(0.0, 500.0), (500.0, 2000.0)])

    def test_attributes_and_textures_survive(self) -> None:
        body = "ATTR_no_blend 0.4\nATTR_poly_os 2\nTRIS 0 6\nATTR_blend\nATTR_shiny_rat 0.3\nTRIS 6 6\n"
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        built = import_obj_file(path, ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lines = [line.split() for line in exported.splitlines() if line.strip()]
        names = [line[0] for line in lines]
        self.assertIn("ATTR_no_blend", names)
        self.assertAlmostEqual(float(next(l for l in lines if l[0] == "ATTR_no_blend")[1]), 0.4, places=4)
        self.assertIn("ATTR_poly_os", names)
        self.assertIn("ATTR_shiny_rat", names)
        self.assertEqual(sum(1 for l in lines if l[0] == "TEXTURE"), 1)
        self.assertTrue(next(l for l in lines if l[0] == "TEXTURE")[1].endswith("tex.png"))

    def test_manipulators_and_light_levels_survive(self) -> None:
        body = (
            "ATTR_light_level 0 1 sim/lit\nATTR_manip_command button sim/cmd/a Do the A\nTRIS 0 6\n"
            "ATTR_manip_none\nATTR_light_level_reset\nATTR_manip_toggle button 1 0 sim/t Flip\nTRIS 6 6\n"
        )
        text = obj_text(body, header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        path = write_file(self.folder.join("part.obj"), text)
        built = import_obj_file(path, ImportOptions(make_exportable=True), ImportReport())
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lines = [line.split() for line in exported.splitlines() if line.strip()]
        self.assertIn(["ATTR_manip_command", "button", "sim/cmd/a", "Do", "the", "A"], lines)
        toggle = next(l for l in lines if l[0] == "ATTR_manip_toggle")
        self.assertEqual((toggle[1], float(toggle[2]), float(toggle[3]), toggle[4], toggle[5]), ("button", 1.0, 0.0, "sim/t", "Flip"))
        self.assertIn(["ATTR_light_level", "0", "1", "sim/lit"], lines)


    def test_detail_textures_become_settings_and_export_again(self) -> None:
        for name in ("leather_decal.png", "grain.png", "panel_mod.png"):
            write_png(self.folder.join(name))
        header = (
            "TEXTURE tex.png\nTEXTURE_MODULATOR panel_mod.png\n"
            "DECAL_PARAMS 4 0 0.5 0 0 0 0 1 0 0 0 0 0 0 grain.png\n"
            "NORMAL_DECAL_PARAMS 6 0 0 0 0 1 0 leather_decal.png 0.74\n"
            "DECAL_PARAMS 2 0.5 0 0 0 0 0 1 0 0 0 0 0 0 grain.png\n"
        )
        text = obj_text("", header=header, vertices=HOUSE_VT, indices=HOUSE_IDX, tris="TRIS 0 6\n")
        built = import_obj_file(write_file(self.folder.join("seat.obj"), text), ImportOptions(make_exportable=True), ImportReport())
        layer = built.collection.xplane.layer
        self.assertEqual("leather_decal.png", os.path.basename(layer.file_normal_decal1))
        self.assertEqual((6.0, 1.0), (layer.normal_decal1_scale, layer.normal_decal1_modulator))
        self.assertEqual((4.0, 0.5, 1.0), (layer.decal1_scale, layer.rgb_decal1_red_key, layer.rgb_decal1_constant))
        self.assertEqual("panel_mod.png", os.path.basename(layer.texture_modulator))
        # A dither the settings can't hold stays an extra line, written back as it was
        self.assertEqual("", layer.file_decal2)
        self.assertEqual(["DECAL_PARAMS"], [a.name for a in layer.customAttributes])

        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        lines = [line.split() for line in exported.splitlines()]
        normal = next(line for line in lines if line[:1] == ["NORMAL_DECAL_PARAMS"])
        self.assertEqual(["6", "0", "0", "0", "0", "1", "0"], [f"{float(v):g}" for v in normal[1:8]])
        self.assertTrue(normal[8].endswith("leather_decal.png"))
        decals = [line for line in lines if line[:1] == ["DECAL_PARAMS"]]
        self.assertEqual(2, len(decals))
        self.assertTrue(any(line[:1] == ["TEXTURE_MODULATOR"] and line[1].endswith("panel_mod.png") for line in lines))

runTestCases([TestImportRoundTrip])
