"""
The X-Plane panels of the Properties editor: every panel, card and menu draws for every kind of object without a
wrong property, operator or icon, and each panel is in its tab
"""

from types import SimpleNamespace

import bpy

from io_xplane2blender import ui
from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout, draw_panel
from io_xplane2blender.ui import menus, motion, object_tab, scene_tab

PANELS = [cls for cls in ui._classes if issubclass(cls, bpy.types.Panel)]
MENUS = [cls for cls in ui._classes if issubclass(cls, bpy.types.Menu)]


def mesh(name: str, collection: str = "Panel") -> bpy.types.Object:
    return test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name, collection=collection)
    )


def make_active(*objects) -> None:
    for obj in bpy.context.view_layer.objects:
        if obj is not None:
            obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0] if objects else None


def draw_everything():
    drawn = {}
    for panel in PANELS:
        layout = draw_panel(panel)
        if layout is not None:
            drawn[panel.__name__] = layout
    for menu in MENUS:
        menu.draw(SimpleNamespace(layout=FakeLayout()), bpy.context)
    return drawn


class TestPanels(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        test_creation_helpers.create_datablock_collection("Panel")
        panel = bpy.data.collections["Panel"]
        panel.xplane.is_exportable_collection = True
        panel.xplane.layer.export_type = C.EXPORT_TYPE_COCKPIT

    def test_draws_with_nothing_selected(self) -> None:
        make_active()
        drawn = draw_everything()
        self.assertNotIn("XPLANE_PT_object", drawn)
        self.assertNotIn("XPLANE_PT_click", drawn)
        self.assertIn("XPLANE_PT_export", drawn)

    def test_every_kind_of_control_draws(self) -> None:
        obj = mesh("knob")
        make_active(obj)
        for manip_type in I.CONTROL_KINDS:
            for opt_in in (False, True):
                for autodetect in (False, True):
                    with self.subTest(manip_type=manip_type, opt_in=opt_in, autodetect=autodetect):
                        obj.xplane.manip.enabled = True
                        obj.xplane.manip.type = manip_type
                        obj.xplane.manip.autodetect_settings_opt_in = opt_in
                        obj.xplane.manip.autodetect_datarefs = autodetect
                        self.assertIn("XPLANE_PT_click", draw_everything())

    def test_every_kind_of_light_draws(self) -> None:
        data = bpy.data.lights.new("lamp", "POINT")
        obj = bpy.data.objects.new("lamp", data)
        bpy.context.scene.collection.objects.link(obj)
        make_active(obj)
        for blender_type in ("POINT", "SPOT", "AREA"):
            for kind, _, _ in menus.LIGHT_KINDS:
                for name in ("", "airplane_landing_core", "airplane_beacon", "not_a_light"):
                    with self.subTest(blender_type=blender_type, kind=kind, name=name):
                        data.type = blender_type
                        data.xplane.type = kind
                        data.xplane.name = name
                        self.assertIn("XPLANE_PT_light", draw_everything())

    def test_every_attachment_draws(self) -> None:
        for kind in (C.EMPTY_USAGE_NONE, C.EMPTY_USAGE_WHEEL, C.EMPTY_USAGE_MAGNET, C.EMPTY_USAGE_EMITTER_PARTICLE):
            obj = bpy.data.objects.new(kind, None)
            bpy.context.scene.collection.objects.link(obj)
            obj.xplane.special_empty_props.special_type = kind
            make_active(obj)
            self.assertIn("XPLANE_PT_attachment", draw_everything())

    def test_animated_and_lit_part_with_every_screen_draws(self) -> None:
        obj = mesh("display")
        make_active(obj)
        bpy.ops.xplane.anim_range(dataref="a321/knob")
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_HIDE)
        obj.xplane.lightLevel = True
        material = bpy.data.materials.new("screen")
        obj.data.materials.append(material)
        layer = bpy.data.collections["Panel"].xplane.layer
        for screen in (C.COCKPIT_FEATURE_NONE, C.COCKPIT_FEATURE_PANEL, C.COCKPIT_FEATURE_DEVICE):
            for mode in (C.PANEL_COCKPIT, C.PANEL_COCKPIT_REGION):
                for blend in (C.BLEND_ON, C.BLEND_OFF, C.BLEND_SHADOW):
                    material.xplane.cockpit_feature = screen
                    material.xplane.lightLevel = True
                    material.xplane.blend_v1000 = blend
                    layer.cockpit_panel_mode = mode
                    layer.cockpit_regions = "2"
                    layer.lods = "2"
                    obj.xplane.override_lods = True
                    drawn = draw_everything()
                    for card in ("XPLANE_PT_motion", "XPLANE_PT_visibility", "XPLANE_PT_glow", "XPLANE_PT_surface", "XPLANE_PT_file"):
                        self.assertIn(card, drawn)
        moves = draw_panel(object_tab.XPLANE_PT_motion)
        self.assertIn("xplane.key_pose", moves.operators())
        self.assertGreaterEqual(moves.operators().count("xplane.go_to_frame"), 2)

    def test_bone_tab(self) -> None:
        armature = bpy.data.armatures.new("arm")
        obj = bpy.data.objects.new("arm", armature)
        bpy.context.scene.collection.objects.link(obj)
        make_active(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        armature.edit_bones.new("lever").tail = (0, 0, 1)
        bpy.ops.object.mode_set(mode="OBJECT")
        armature.bones.active = armature.bones["lever"]
        self.assertEqual("Not animated", draw_panel(motion.XPLANE_PT_bone).labels()[0][:12])
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_TRANSFORM, target="bone")
        bpy.ops.xplane.add_dataref(anim_type=C.ANIM_TYPE_SHOW, target="bone")
        self.assertEqual(2, len(armature.bones["lever"].xplane.datarefs))
        self.assertIn("xplane.key_pose", draw_panel(motion.XPLANE_PT_bone).operators())
        self.assertIn("show_hide_v1", draw_panel(motion.XPLANE_PT_bone_visibility).props())
        bpy.ops.xplane.remove_dataref(index=0, target="bone")
        self.assertEqual(1, len(armature.bones["lever"].xplane.datarefs))

    def test_several_selected_offer_copying(self) -> None:
        a, b = mesh("a"), mesh("b")
        a.xplane.manip.enabled = True
        make_active(a, b)
        self.assertIn("xplane.copy_to_selected", draw_panel(object_tab.XPLANE_PT_click).operators())
        self.assertTrue(any("2 selected" in text for text in draw_panel(object_tab.XPLANE_PT_object).labels()))

    def test_files_list(self) -> None:
        mesh("in file")
        test_creation_helpers.create_datablock_collection("Not a file")
        ul = SimpleNamespace(filter_name="", bitflag_filter_item=1 << 30)
        flags, _ = scene_tab.XPLANE_UL_files.filter_items(ul, bpy.context, bpy.data, "collections")
        self.assertEqual(["Panel"], [c.name for c, f in zip(bpy.data.collections, flags) if f])
        # Imported OBJs have their settings filled in but are not ticked: they are listed, ready to tick
        bpy.data.collections["Not a file"].xplane.layer.name = "imported_part"
        flags, _ = scene_tab.XPLANE_UL_files.filter_items(ul, bpy.context, bpy.data, "collections")
        self.assertEqual(2, sum(1 for f in flags if f))
        bpy.data.collections["Not a file"].xplane.layer.name = ""
        bpy.context.window_manager.xplane_panels.show_all_collections = True
        flags, _ = scene_tab.XPLANE_UL_files.filter_items(ul, bpy.context, bpy.data, "collections")
        self.assertEqual(2, sum(1 for f in flags if f))
        for collection in bpy.data.collections:
            scene_tab.XPLANE_UL_files.draw_item(ul, bpy.context, FakeLayout(), bpy.data, collection, 0, None, "", 0)

    def test_each_panel_is_in_its_tab(self) -> None:
        tabs = {
            "XPLANE_PT_object": "object",
            "XPLANE_PT_click": "object",
            "XPLANE_PT_light": "object",
            "XPLANE_PT_bone": "bone",
            "XPLANE_PT_surface": "material",
            "XPLANE_PT_collection": "collection",
            "XPLANE_PT_export": "scene",
            "XPLANE_PT_file": "scene",
            "XPLANE_PT_check": "scene",
            "XPLANE_PT_tools": "scene",
            "VIEW3D_PT_xplane_bulk_edit": "scene",
            "XPLANE_PT_table": "scene",
        }
        for name, tab in tabs.items():
            panel = getattr(bpy.types, name)
            self.assertEqual(("PROPERTIES", tab), (panel.bl_space_type, panel.bl_context), name)
        # Upstream XPlane2Blender's panels are gone
        for name in ("OBJECT_PT_xplane", "MATERIAL_PT_xplane", "DATA_PT_xplane", "SCENE_PT_xplane", "BONE_PT_xplane"):
            self.assertFalse(hasattr(bpy.types, name), name)

    def test_collection_tab(self) -> None:
        panel_layer = bpy.context.view_layer.layer_collection.children["Panel"]
        bpy.context.view_layer.active_layer_collection = panel_layer
        layout = draw_panel(scene_tab.XPLANE_PT_collection)
        self.assertIn("xplane.show_file", layout.operators())
        self.assertIn("name", layout.props())


runTestCases([TestPanels])
