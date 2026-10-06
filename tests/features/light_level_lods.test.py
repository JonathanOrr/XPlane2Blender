import bpy

from io_xplane2blender.tests import XPlaneTestCase, runTestCases, test_creation_helpers
from io_xplane2blender.xplane_constants import (
    BLEND_OFF,
    EXPORT_TYPE_AIRCRAFT,
    EXPORT_TYPE_INSTANCED_SCENERY,
    VERSION_1200,
)

DATAREF = "sim/flightmodel2/misc/custom_slider_ratio[0]"


class TestLightLevelLODs(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        bpy.ops.wm.read_homefile(use_empty=True)
        bpy.context.scene.xplane.version = VERSION_1200
        self.root = test_creation_helpers.create_datablock_collection("LightLevels")
        self.root.xplane.layer.export_type = EXPORT_TYPE_AIRCRAFT

    def _lods(self):
        layer = self.root.xplane.layer
        layer.lods = "3"
        for i, far in enumerate((2, 4, 6)):
            layer.lod[i].near = 0
            layer.lod[i].far = far

    def _mesh(self, name, parent=None, material="Material"):
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", name, collection=self.root),
            material_name=material,
        )
        obj.parent = parent
        if self.root.xplane.layer.lods != "0":
            obj.xplane.override_lods = True
            obj.xplane.lod = (True, True, True, False)
        return obj

    def _check_light_levels(self, expected, photometric=False):
        bpy.context.view_layer.update()
        out = self.exportExportableRoot(self.root)
        self.assertLoggerErrors(0)
        current = None
        levels = []
        lod_count = 0
        for line in out.splitlines():
            tokens = line.split()
            if not tokens:
                continue
            if tokens[0] == "ATTR_LOD":
                # OBJ8 starts each LOD with default state, regardless of the previous one.
                current = None
                lod_count += 1
            elif tokens[0] == "ATTR_light_level":
                current = tokens[3]
                if photometric:
                    self.assertEqual(["0", "1", DATAREF, "1000"], tokens[1:])
            elif tokens[0] == "ATTR_light_level_reset":
                current = None
            elif tokens[0] == "TRIS":
                levels.append(current)
        self.assertEqual(int(self.root.xplane.layer.lods), lod_count)
        self.assertEqual(expected, levels, out)
        return out

    def test_material_light_level_in_each_lod(self):
        self._lods()
        obj = self._mesh("Mesh")
        obj.data.materials[0].xplane.lightLevel = True
        obj.data.materials[0].xplane.lightLevel_dataref = DATAREF
        self._check_light_levels([DATAREF] * 3)

    def test_photometric_light_level_on_distinct_lod_meshes(self):
        self._lods()
        for i in range(3):
            obj = self._mesh(f"Mesh{i}")
            obj.xplane.lod = (False,) * 4
            obj.xplane.lod[i] = True
            mat = obj.data.materials[0].xplane
            mat.lightLevel = True
            mat.lightLevel_dataref = DATAREF
            mat.lightLevel_photometric = True
            mat.lightLevel_brightness = 1000
        self._check_light_levels([DATAREF] * 3, photometric=True)

    def test_object_light_level_in_each_lod(self):
        self._lods()
        obj = self._mesh("Mesh")
        obj.xplane.lightLevel = True
        obj.xplane.lightLevel_dataref = DATAREF
        self._check_light_levels([DATAREF] * 3)

    def test_registered_custom_resetter_survives_lod_boundaries(self):
        self._lods()
        obj = self._mesh("AMesh")
        attr = obj.xplane.customAttributes.add()
        attr.name = "TEST_custom_set"
        attr.value = "1"
        attr.reset = "TEST_custom_reset"
        # The final mesh's state must be emitted again in the next LOD, while
        # the registered setter/resetter pair continues to work within each LOD.
        final_mesh = self._mesh("ZMesh")
        persistent = final_mesh.xplane.customAttributes.add()
        persistent.name = "TEST_lod_state"
        persistent.value = "2"
        out = self._check_light_levels([None] * 6)
        commands = [line.split()[0] for line in out.splitlines() if line.strip()]
        self.assertEqual(3, commands.count("TEST_lod_state"))
        self.assertEqual(3, commands.count("TEST_custom_set"))
        self.assertEqual(3, commands.count("TEST_custom_reset"))

    def test_lods_keep_header_global_defaults(self):
        self._lods()
        self.root.xplane.layer.export_type = EXPORT_TYPE_INSTANCED_SCENERY
        obj = self._mesh("Mesh")
        obj.data.materials[0].xplane.blend_v1000 = BLEND_OFF
        attr = obj.xplane.customAttributes.add()
        attr.name = "TEST_lod_state"
        attr.value = "1"
        out = self._check_light_levels([None] * 3)
        commands = [line.split()[0] for line in out.splitlines() if line.strip()]
        self.assertEqual(3, commands.count("TEST_lod_state"))
        self.assertIn("GLOBAL_no_blend", commands)
        self.assertIn("GLOBAL_specular", commands)
        self.assertNotIn("ATTR_no_blend", commands)
        self.assertNotIn("ATTR_shiny_rat", commands)

    def test_default_lod_does_not_reset_previous_lod_state(self):
        self._lods()
        for i in range(3):
            obj = self._mesh(f"Mesh{i}", material=f"Material{i}")
            obj.xplane.lod = (False,) * 4
            obj.xplane.lod[i] = True
            if i == 0:
                obj.data.materials[0].xplane.lightLevel = True
                obj.data.materials[0].xplane.lightLevel_dataref = DATAREF
        out = self._check_light_levels([DATAREF, None, None])
        self.assertNotIn("ATTR_light_level_reset", out)


runTestCases([TestLightLevelLODs])
