"""
Light authoring helpers: what a lights.txt light is, which parameters a Manual Param light takes,
and a viewport preview that never changes the export
"""

import os

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_light_tools
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser as parser

__dirname__ = os.path.dirname(__file__)


def find_light(spills: bool, glows: bool, takes_params: bool) -> str:
    parser.parse_lights_file()
    for name in sorted(parser._parsed_lights_txt_content):
        parsed = parser.get_parsed_light(name)
        if (
            xplane_light_tools.kinds_of(name) == (spills, glows)
            and bool(parsed.light_param_def) == takes_params
            and parser.is_automatic_light_compatible(name)
        ):
            return name
    raise AssertionError(f"lights.txt has no light with spills={spills} glows={glows} params={takes_params}")


def light(name: str, xplane_type: str, blender_type: str = "POINT", collection: str = "Layer 1") -> bpy.types.Object:
    obj = test_creation_helpers.create_datablock_light(
        test_creation_helpers.DatablockInfo("LIGHT", name, collection=collection, location=Vector((0, 0, 1))),
        blender_type,
    )
    obj.data.xplane.type = xplane_type
    return obj


class TestLightTools(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()

    def test_describes_what_a_light_is(self) -> None:
        spill = find_light(spills=True, glows=False, takes_params=False)
        glow = find_light(spills=False, glows=True, takes_params=False)
        self.assertTrue(xplane_light_tools.describe(spill).startswith("Spill"))
        self.assertTrue(xplane_light_tools.describe(glow).startswith("Glow:"))
        self.assertIn("check the spelling", xplane_light_tools.describe("no_such_light"))
        self.assertFalse(xplane_light_tools.is_known("no_such_light"))

    def test_param_lights_say_what_they_need(self) -> None:
        name = find_light(spills=False, glows=True, takes_params=True)
        wanted = list(parser.get_parsed_light(name).light_param_def)
        self.assertEqual(
            (wanted, f"Needs {len(wanted)} value(s), has 1"), xplane_light_tools.param_check(name, "1")
        )
        self.assertEqual((wanted, ""), xplane_light_tools.param_check(name, " ".join(["1"] * len(wanted))))
        plain = find_light(spills=False, glows=True, takes_params=False)
        self.assertIn("Named", xplane_light_tools.param_check(plain, "")[1])

    def test_picking_a_name(self) -> None:
        obj = light("lamp", "named")
        bpy.context.view_layer.objects.active = obj
        name = find_light(spills=True, glows=False, takes_params=False)
        self.assertEqual({"FINISHED"}, bpy.ops.xplane.light_pick_name(light=name))
        self.assertEqual(name, obj.data.xplane.name)

    def test_preview_lights_spills_and_darkens_glows(self) -> None:
        spill = light("spill", "named")
        spill.data.xplane.name = find_light(spills=True, glows=False, takes_params=False)
        glow = light("glow", "named")
        glow.data.xplane.name = find_light(spills=False, glows=True, takes_params=False)
        custom_spill = light("flood", "light_spill_custom", "SPOT")
        custom_spill.data.xplane.size = 2.5
        halo = light("halo", "custom")
        halo.data.energy = 0.7
        unknown = light("typo", "named")
        unknown.data.xplane.name = "no_such_light"
        unknown.data.energy = 3.0

        self.assertEqual({"FINISHED"}, bpy.ops.xplane.lights_preview(selected_only=False))

        self.assertGreater(spill.data.energy, 0.0)
        self.assertTrue(spill.visible_diffuse)
        self.assertEqual(0.0, glow.data.energy)
        self.assertFalse(glow.visible_diffuse)
        self.assertGreater(custom_spill.data.energy, 0.0)
        if hasattr(custom_spill.data, "use_custom_distance"):
            self.assertTrue(custom_spill.data.use_custom_distance)
            self.assertAlmostEqual(2.5, custom_spill.data.cutoff_distance, places=4)
        self.assertFalse(halo.visible_diffuse)
        self.assertAlmostEqual(0.7, halo.data.energy, places=5)  # A custom light's power is its exported alpha
        self.assertAlmostEqual(3.0, unknown.data.energy, places=5)

    def test_preview_never_changes_the_export(self) -> None:
        test_creation_helpers.create_datablock_collection("Layer 1")
        spill = light("spill", "named")
        spill.data.xplane.name = find_light(spills=True, glows=False, takes_params=False)
        glow = light("glow", "named")
        glow.data.xplane.name = find_light(spills=False, glows=True, takes_params=False)
        param = light("param", "param")
        param_name = find_light(spills=False, glows=True, takes_params=True)
        param.data.xplane.name = param_name
        param.data.xplane.params = " ".join(["0.5"] * len(parser.get_parsed_light(param_name).light_param_def))
        custom_spill = light("flood", "light_spill_custom", "SPOT")
        custom_spill.data.xplane.size = 2.5
        halo = light("halo", "custom")
        halo.data.energy = 0.7
        mesh = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "panel", collection="Layer 1")
        )
        before = self.exportExportableRoot("Layer 1")

        bpy.ops.xplane.lights_preview(selected_only=False, strength=5.0)

        self.assertEqual(before, self.exportExportableRoot("Layer 1"))
        self.assertIn("LIGHT_SPILL_CUSTOM", before)
        self.assertIn("LIGHT_CUSTOM", before)


runTestCases([TestLightTools])
