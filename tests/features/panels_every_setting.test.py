"""
Every X-Plane setting has a place in the panels: drawing them for every kind of object, control, light, screen
and file option shows each setting at least once, so nothing can only be set from Python
"""

import bpy

from io_xplane2blender import ui, xplane_props
from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import draw_panel
from io_xplane2blender.ui import menus

PANELS = [cls for cls in ui._classes if issubclass(cls, bpy.types.Panel)]

# Shown as text rather than as settings
NOT_SETTINGS = {"XPlane2BlenderVersion"}
# Picked from a menu of plain-worded kinds, which sets them
FROM_MENUS = {"XPlaneLightSettings.type", "XPlaneManipulatorSettings.type"}


def every_setting():
    for cls in xplane_props._classes:
        if cls.__name__ in NOT_SETTINGS:
            continue
        for prop in cls.bl_rna.properties:
            # Every property group has Blender's own "name", only some use it
            builtin = prop.identifier == "name" and "name" not in cls.__annotations__
            if prop.identifier != "rna_type" and prop.type not in {"POINTER", "COLLECTION"} and not builtin:
                setting = f"{cls.bl_rna.identifier}.{prop.identifier}"
                if setting not in FROM_MENUS:
                    yield setting


def make_active(obj) -> None:
    for other in bpy.context.view_layer.objects:
        other.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


class TestEverySettingHasAPlace(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        self.drawn = set()

    def draw(self) -> None:
        for panel in PANELS:
            layout = draw_panel(panel)
            if layout is not None:
                self.drawn.update(layout.settings())

    def link(self, obj) -> bpy.types.Object:
        if obj.name not in bpy.data.collections["Cockpit"].objects:
            bpy.data.collections["Cockpit"].objects.link(obj)
        make_active(obj)
        return obj

    def file_states(self) -> None:
        layer = bpy.data.collections["Cockpit"].xplane.layer
        layer.customAttributes.add()
        for mode in (C.PANEL_COCKPIT, C.PANEL_COCKPIT_REGION):
            layer.cockpit_panel_mode = mode
            layer.cockpit_regions = "1"
            layer.lods = "1"
            rain = layer.rain
            for i in range(1, 5):
                setattr(rain, f"thermal_source_{i}_enabled", True)
                setattr(rain, f"wiper_{i}_enabled", True)
            for i in (1, 2):
                setattr(layer, f"file_decal{i}", f"//decal{i}.png")
                setattr(layer, f"file_normal_decal{i}", f"//normal_decal{i}.png")
            for projected in (False, True):
                for i in (1, 2):
                    setattr(layer, f"decal{i}_projected", projected)
                    setattr(layer, f"normal_decal{i}_projected", projected)
                self.draw()
        bpy.context.scene.xplane.debug = True
        bpy.context.scene.xplane.plugin_development = True
        self.draw()

    def mesh_states(self) -> None:
        obj = self.link(test_creation_helpers.create_datablock_mesh(test_creation_helpers.DatablockInfo("MESH", "part")))
        bpy.data.collections["Cockpit"].xplane.layer.lods = "2"
        x = obj.xplane
        x.override_lods = True
        x.lightLevel = True
        x.customAttributes.add()
        x.customAnimAttributes.add()
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM)
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_SHOW)
        material = bpy.data.materials.new("screen")
        obj.data.materials.clear()
        obj.data.materials.append(material)
        material.xplane.lightLevel = True
        material.xplane.customAttributes.add()
        material.xplane.surfaceType = C.SURFACE_TYPE_CONCRETE
        x.manip.enabled = True
        x.manip.axis_detent_ranges.add()
        for manip_type in I.CONTROL_KINDS:
            for opt_in in (False, True):
                for autodetect in (False, True):
                    x.manip.type = manip_type
                    x.manip.autodetect_settings_opt_in = opt_in
                    x.manip.autodetect_datarefs = autodetect
                    self.draw()
        for feature in (C.COCKPIT_FEATURE_NONE, C.COCKPIT_FEATURE_PANEL, C.COCKPIT_FEATURE_DEVICE):
            for blend in (C.BLEND_ON, C.BLEND_OFF):
                for device in (C.DEVICE_GNS430_1, C.DEVICE_PLUGIN):
                    material.xplane.cockpit_feature = feature
                    material.xplane.blend_v1000 = blend
                    material.xplane.device_name = device
                    self.draw()
        x.override_weight = True
        x.isExportableRoot = True
        self.draw()

    def light_states(self) -> None:
        data = bpy.data.lights.new("lamp", "SPOT")
        self.link(bpy.data.objects.new("lamp", data))
        data.xplane.customAttributes.add()
        for kind, _, _ in menus.LIGHT_KINDS:
            # Library lights with flashing, intensity and no parameters
            for name in ("airplane_beacon_rotate", "airplane_beacon_rotate_sp", "airplane_landing_bb", "airplane_beacon"):
                for blender_type in ("POINT", "SPOT"):
                    for rgb_override in (False, True):
                        data.type = blender_type
                        data.xplane.type = kind
                        data.xplane.name = name
                        data.xplane.enable_rgb_override = rgb_override
                        self.draw()

    def empty_states(self) -> None:
        obj = self.link(bpy.data.objects.new("empty", None))
        for kind in (C.EMPTY_USAGE_WHEEL, C.EMPTY_USAGE_MAGNET, C.EMPTY_USAGE_EMITTER_PARTICLE):
            obj.xplane.special_empty_props.special_type = kind
            self.draw()

    def bone_states(self) -> None:
        armature = bpy.data.armatures.new("arm")
        self.link(bpy.data.objects.new("arm", armature))
        bpy.ops.object.mode_set(mode="EDIT")
        armature.edit_bones.new("lever").tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")
        armature.bones.active = armature.bones["lever"]
        bone = armature.bones["lever"].xplane
        bone.customAttributes.add()
        bone.customAnimAttributes.add()
        bone.override_weight = True
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM, target="bone")
        self.draw()

    def test_every_setting_is_drawn_somewhere(self) -> None:
        test_creation_helpers.create_datablock_collection("Cockpit")
        cockpit = bpy.data.collections["Cockpit"]
        cockpit.xplane.is_exportable_collection = True
        cockpit.xplane.layer.export_type = C.EXPORT_TYPE_COCKPIT
        bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children["Cockpit"]
        self.file_states()
        self.mesh_states()
        self.light_states()
        self.empty_states()
        self.bone_states()
        missing = sorted(set(every_setting()) - self.drawn)
        self.maxDiff = None
        self.assertEqual([], missing)


runTestCases([TestEverySettingHasAPlace])
