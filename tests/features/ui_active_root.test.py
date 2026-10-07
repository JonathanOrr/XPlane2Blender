import os

import bpy

from io_xplane2blender import xplane_helpers
from io_xplane2blender.tests import *

__dirname__ = os.path.dirname(__file__)


class TestUINoActiveObject(XPlaneTestCase):
    def test_no_active_object_and_no_collection_returns_none(self) -> None:
        self.assertIsNone(xplane_helpers.get_active_export_root(None, None))

    def test_non_root_object_returns_none(self) -> None:
        obj = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Not A Root")
        )
        self.assertFalse(obj.xplane.isExportableRoot)
        self.assertIsNone(xplane_helpers.get_active_export_root(obj, None))

    def test_root_object_is_returned(self) -> None:
        obj = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Root Object")
        )
        obj.xplane.isExportableRoot = True
        self.assertIs(obj, xplane_helpers.get_active_export_root(obj, None))

    def test_exportable_collection_is_returned(self) -> None:
        non_root = test_creation_helpers.create_datablock_empty(
            test_creation_helpers.DatablockInfo("EMPTY", "Not A Root")
        )
        coll = test_creation_helpers.create_datablock_collection("Layer 1")
        coll.xplane.is_exportable_collection = True
        self.assertIs(coll, xplane_helpers.get_active_export_root(non_root, coll))


runTestCases([TestUINoActiveObject])
