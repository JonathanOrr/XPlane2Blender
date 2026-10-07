import os
import types

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.xplane_constants import EXPORT_TYPE_AIRCRAFT
from io_xplane2blender.xplane_ops_wiper import XPLANE_OT_bake_wiper_gradient_texture

__dirname__ = os.path.dirname(__file__)


class FakeBakeContext:
    """The context the bake op sees when no root is active, e.g. a fresh empty scene"""

    def __init__(self, scene, active_object=None, collection=None):
        self.scene = scene
        self.active_object = active_object
        self.collection = collection


class TestBakeOpsNoActiveRoot(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        self._original_engine = bpy.context.scene.render.engine
        bpy.context.scene.render.engine = "CYCLES"

    def tearDown(self):
        bpy.context.scene.render.engine = self._original_engine
        super().tearDown()

    def test_execute_no_active_object_cancels_and_reports_error(self) -> None:
        ctx = FakeBakeContext(bpy.context.scene)
        ret = XPLANE_OT_bake_wiper_gradient_texture.execute(
            types.SimpleNamespace(), ctx
        )
        self.assertEqual(ret, {"CANCELLED"})
        self.assertLoggerErrors(1)

    def test_execute_no_exportable_root_cancels_and_reports_error(self) -> None:
        not_a_root = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Not A Root")
        )
        coll = test_creation_helpers.create_datablock_collection("Layer 1")
        coll.xplane.is_exportable_collection = False
        ctx = FakeBakeContext(
            bpy.context.scene, active_object=not_a_root, collection=coll
        )
        ret = XPLANE_OT_bake_wiper_gradient_texture.execute(
            types.SimpleNamespace(), ctx
        )
        self.assertEqual(ret, {"CANCELLED"})
        self.assertLoggerErrors(1)

    def test_poll_no_active_object_returns_false(self) -> None:
        ctx = FakeBakeContext(bpy.context.scene)
        self.assertFalse(XPLANE_OT_bake_wiper_gradient_texture.poll(ctx))

    def test_poll_exportable_aircraft_root_returns_true(self) -> None:
        root = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Aircraft Root")
        )
        root.xplane.isExportableRoot = True
        root.xplane.layer.export_type = EXPORT_TYPE_AIRCRAFT
        ctx = FakeBakeContext(bpy.context.scene, active_object=root)
        self.assertTrue(XPLANE_OT_bake_wiper_gradient_texture.poll(ctx))


runTestCases([TestBakeOpsNoActiveRoot])
