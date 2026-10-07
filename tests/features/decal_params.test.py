import os

import bpy

from io_xplane2blender.tests import *

__dirname__ = os.path.dirname(__file__)


class TestDecalParams(XPlaneTestCase):
    def test_decal_constant_strength_exported_per_slot(self) -> None:
        coll = test_creation_helpers.create_datablock_collection("Layer 1")
        layer = coll.xplane.layer

        for slot, (modulator, constant) in ((1, (0.25, 0.75)), (2, (0.5, 0.125))):
            setattr(layer, f"file_decal{slot}", f"//decal{slot}.png")
            setattr(layer, f"alpha_decal{slot}_modulator", modulator)
            setattr(layer, f"alpha_decal{slot}_constant", constant)

        out = self.exportLayer(0)
        decal_params = [
            line.split()
            for line in out.splitlines()
            if line.split()[:1] == ["DECAL_PARAMS"]
        ]

        self.assertEqual(2, len(decal_params), out)
        for (slot, modulator, constant), params in zip(
            ((1, 0.25, 0.75), (2, 0.5, 0.125)), decal_params
        ):
            # DECAL_PARAMS <scale> <dither> <rgb keys x4> <rgb mod> <rgb const>
            #              <alpha keys x4> <alpha mod> <alpha const> <file>
            self.assertEqual(f"decal{slot}.png", params[-1])
            self.assertAlmostEqual(modulator, float(params[-3]), msg=f"slot {slot}")
            self.assertAlmostEqual(constant, float(params[-2]), msg=f"slot {slot}")


runTestCases([TestDecalParams])
