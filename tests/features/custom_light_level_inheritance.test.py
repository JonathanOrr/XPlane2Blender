import bpy

from io_xplane2blender.tests import XPlaneTestCase, runTestCases, test_creation_helpers
from io_xplane2blender.xplane_constants import EXPORT_TYPE_AIRCRAFT

DATAREF = "sim/flightmodel2/misc/custom_slider_ratio[0]"
OVERRIDE = "sim/test/override_light_level"


class TestCustomLightLevelInheritance(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        bpy.ops.wm.read_homefile(use_empty=True)
        self.root = test_creation_helpers.create_datablock_collection("LightLevels")
        self.root.xplane.layer.export_type = EXPORT_TYPE_AIRCRAFT

    def _mesh(self, name, parent=None, material="Material"):
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", name, collection=self.root),
            material_name=material,
        )
        obj.parent = parent
        return obj

    def _custom_parent(self):
        parent = self._mesh("AParent")
        attr = parent.xplane.customAttributes.add()
        attr.name = "ATTR_light_level"
        attr.value = f"0 1 {DATAREF}"
        self._mesh("Child1", parent)
        self._mesh("Child2", parent)
        return parent

    def _check_light_levels(self, expected):
        bpy.context.view_layer.update()
        out = self.exportExportableRoot(self.root)
        self.assertLoggerErrors(0)
        current = None
        levels = []
        for line in out.splitlines():
            tokens = line.split()
            if not tokens:
                continue
            if tokens[0] == "ATTR_light_level":
                current = tokens[3]
            elif tokens[0] == "ATTR_light_level_reset":
                current = None
            elif tokens[0] == "TRIS":
                levels.append(current)
        self.assertEqual(expected, levels, out)

    def test_custom_parent_light_level_covers_children(self):
        self._custom_parent()
        self._check_light_levels([DATAREF] * 3)

    def test_child_material_override_then_parent_level_restored(self):
        parent = self._custom_parent()
        child = bpy.data.objects["Child1"]
        test_creation_helpers.set_material(child, "Override")
        child.data.materials[0].xplane.lightLevel = True
        child.data.materials[0].xplane.lightLevel_dataref = OVERRIDE
        # Explicit ordering keeps the override before the default child.
        child.xplane.override_weight = True
        child.xplane.weight = 0
        bpy.data.objects["Child2"].xplane.override_weight = True
        bpy.data.objects["Child2"].xplane.weight = 1
        self.assertIs(child.parent, parent)
        self._check_light_levels([DATAREF, OVERRIDE, DATAREF])

    def test_child_object_override_then_parent_level_restored(self):
        self._custom_parent()
        child = bpy.data.objects["Child1"]
        child.xplane.lightLevel = True
        child.xplane.lightLevel_dataref = OVERRIDE
        self._check_light_levels([DATAREF, OVERRIDE, DATAREF])

    def test_custom_parent_level_resets_for_unrelated_mesh(self):
        self._custom_parent()
        self._mesh("ZUnrelated")
        self._check_light_levels([DATAREF, DATAREF, DATAREF, None])

    def test_explicit_custom_reset_stops_inheritance(self):
        self._custom_parent()
        child = bpy.data.objects["Child1"]
        attr = child.xplane.customAttributes.add()
        attr.name = "ATTR_light_level_reset"
        self._mesh("Grandchild", child)
        self._check_light_levels([DATAREF, None, None, DATAREF])


runTestCases([TestCustomLightLevelInheritance])
