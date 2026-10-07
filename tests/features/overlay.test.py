"""
The viewport overlay's labels and click zone outlines (drawing itself needs a window, so only the data is checked)
"""

from types import SimpleNamespace

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_overlay
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

    def test_overlay_popover_draws(self) -> None:
        xplane_overlay.overlay_popover(SimpleNamespace(layout=FakeLayout()), bpy.context)


runTestCases([TestOverlay])
