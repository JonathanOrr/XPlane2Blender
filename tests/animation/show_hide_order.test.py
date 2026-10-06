import bpy

from io_xplane2blender.tests import XPlaneTestCase, runTestCases, test_creation_helpers
from io_xplane2blender.xplane_constants import EXPORT_TYPE_AIRCRAFT
from io_xplane2blender.xplane_types.xplane_object import XPlaneObject


class TestShowHideOrder(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        bpy.ops.wm.read_homefile(use_empty=True)
        self.root = test_creation_helpers.create_datablock_collection("ShowHideOrder")
        self.root.xplane.layer.export_type = EXPORT_TYPE_AIRCRAFT

    def _mesh(self):
        return test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "Mesh", collection=self.root)
        )

    def _datarefs(self, owner):
        for path, anim_type in (
            ("dref_1", "show"),
            ("dref_2", "hide"),
            ("dref_3", "show"),
        ):
            dataref = owner.xplane.datarefs.add()
            dataref.path = path
            dataref.anim_type = anim_type
            dataref.show_hide_v1 = 0
            dataref.show_hide_v2 = 1

    def _custom_attributes(self, obj, attributes):
        for name, value in attributes:
            attr = obj.xplane.customAnimAttributes.add()
            attr.name = name
            attr.value = value

    def _export(self):
        bpy.context.view_layer.update()
        out = self.exportExportableRoot(self.root)
        self.assertLoggerErrors(0)
        return out

    def _assert_order(self, repeats=1):
        out = self._export()
        actual = [
            (tokens[0], tokens[3])
            for line in out.splitlines()
            if (tokens := line.split()) and tokens[0] in {"ANIM_show", "ANIM_hide"}
        ]
        self.assertEqual(
            [("ANIM_show", "dref_1"), ("ANIM_hide", "dref_2"), ("ANIM_show", "dref_3")]
            * repeats,
            actual,
            out,
        )

    def test_object_datarefs_preserve_show_hide_show_order(self):
        obj = self._mesh()
        self._datarefs(obj)
        test_creation_helpers.set_animation_data(
            obj, test_creation_helpers.T_2_FRAMES_1_X
        )
        self._assert_order()

    def test_custom_animation_attributes_preserve_show_hide_show_order(self):
        obj = self._mesh()
        self._custom_attributes(
            obj,
            (
                ("ANIM_show", "0 1 dref_1"),
                ("ANIM_hide", "0 1 dref_2"),
                ("ANIM_show", "0 1 dref_3"),
            ),
        )
        test_creation_helpers.set_animation_data(
            obj, test_creation_helpers.T_2_FRAMES_1_X
        )
        self._assert_order()

    def test_custom_and_builtin_occurrences_do_not_collide(self):
        obj = self._mesh()
        self._custom_attributes(
            obj,
            (
                ("ANIM_show", "0 1 dref_1"),
                ("ANIM_hide", "0 1 dref_2"),
                ("ANIM_show", "0 1 dref_3"),
            ),
        )
        # Matching commands and ranges must survive as two ordered sequences,
        # even when custom and built-in entries have the same list indices.
        self._datarefs(obj)
        self._assert_order(repeats=2)

    def test_ordinary_custom_animation_attributes_still_merge(self):
        obj = self._mesh()
        self._custom_attributes(
            obj,
            (
                ("ANIM_keyframe_loop", "1"),
                ("ANIM_hide", "0 1 dref_2"),
                ("ANIM_keyframe_loop", "2"),
                ("ANIM_keyframe_loop", "1"),
            ),
        )
        xplane_object = XPlaneObject(obj)
        xplane_object.collectAnimAttributes()
        attr = xplane_object.animAttributes["ANIM_keyframe_loop"]
        self.assertIs(type(attr.name), str)
        self.assertEqual(["1", "2"], attr.getValues())
        out = self._export()
        actual = [
            tokens
            for line in out.splitlines()
            if (tokens := line.split())
            and tokens[0] in {"ANIM_keyframe_loop", "ANIM_hide"}
        ]
        self.assertEqual(
            [
                ["ANIM_keyframe_loop", "1"],
                ["ANIM_keyframe_loop", "2"],
                ["ANIM_hide", "0", "1", "dref_2"],
            ],
            actual,
            out,
        )


runTestCases([TestShowHideOrder])
