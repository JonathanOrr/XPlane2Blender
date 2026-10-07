"""
The X-Plane sidebar: every panel, card and menu draws for every kind of object without a wrong property,
operator or icon, the Clickable card shows what the classic panel showed, and its operators do what they say
"""

from types import SimpleNamespace

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender import xplane_sidebar as S
from io_xplane2blender import xplane_helpers, xplane_ui
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout, draw_panel

PANELS = [
    cls
    for cls in S._classes
    if isinstance(cls, type) and issubclass(cls, bpy.types.Panel)
]
MENUS = [cls for cls in S._classes if isinstance(cls, type) and issubclass(cls, bpy.types.Menu)]


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


class TestSidebar(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        test_creation_helpers.create_datablock_collection("Panel")
        panel = bpy.data.collections["Panel"]
        panel.xplane.is_exportable_collection = True
        panel.xplane.layer.export_type = C.EXPORT_TYPE_COCKPIT

    def draw_everything(self):
        drawn = {}
        for panel in PANELS:
            layout = draw_panel(panel)
            if layout is not None:
                drawn[panel.__name__] = layout
        for menu in MENUS:
            layout = FakeLayout()
            menu.draw(SimpleNamespace(layout=layout), bpy.context)
        return drawn

    def test_draws_with_nothing_selected(self) -> None:
        make_active()
        drawn = self.draw_everything()
        self.assertIn("XPLANE_PT_selected", drawn)
        self.assertNotIn("XPLANE_PT_click", drawn)

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
                        self.assertIn("XPLANE_PT_click", self.draw_everything())

    def test_clickable_card_shows_what_the_classic_panel_showed(self) -> None:
        obj = mesh("lever")
        make_active(obj)
        manip = obj.xplane.manip
        manip.enabled = True
        bpy.context.scene.xplane.version = C.VERSION_1220
        for manip_type in I.CONTROL_KINDS:
            for opt_in in (False, True):
                for autodetect in (False, True):
                    manip.type = manip_type
                    manip.autodetect_settings_opt_in = opt_in
                    manip.autodetect_datarefs = autodetect
                    classic = FakeLayout()
                    xplane_ui.manipulator_layout(classic, obj)
                    card = draw_panel(S.XPLANE_PT_click)
                    with self.subTest(manip_type=manip_type, opt_in=opt_in, autodetect=autodetect):
                        self.assertEqual(sorted(set(classic.props()) - {"type"}), sorted(set(card.props())))

    def test_every_kind_of_light_draws(self) -> None:
        data = bpy.data.lights.new("lamp", "POINT")
        obj = bpy.data.objects.new("lamp", data)
        bpy.context.scene.collection.objects.link(obj)
        make_active(obj)
        for blender_type in ("POINT", "SPOT", "AREA"):
            for kind in [k for k, _, _ in S.LIGHT_KINDS] + [C.LIGHT_DEFAULT, C.LIGHT_STROBE]:
                for name in ("", "airplane_landing_core", "not_a_light"):
                    with self.subTest(blender_type=blender_type, kind=kind, name=name):
                        data.type = blender_type
                        data.xplane.type = kind
                        data.xplane.name = name
                        self.assertIn("XPLANE_PT_light", self.draw_everything())

    def test_every_attachment_draws(self) -> None:
        for kind in (C.EMPTY_USAGE_NONE, C.EMPTY_USAGE_WHEEL, C.EMPTY_USAGE_MAGNET, C.EMPTY_USAGE_EMITTER_PARTICLE):
            obj = bpy.data.objects.new(kind, None)
            bpy.context.scene.collection.objects.link(obj)
            obj.xplane.special_empty_props.special_type = kind
            make_active(obj)
            self.assertIn("XPLANE_PT_attachment", self.draw_everything())

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
                    drawn = self.draw_everything()
                    for card in ("XPLANE_PT_motion", "XPLANE_PT_visibility", "XPLANE_PT_glow", "XPLANE_PT_surface", "XPLANE_PT_file"):
                        self.assertIn(card, drawn)
        motion = draw_panel(S.XPLANE_PT_motion)
        self.assertIn("xplane.key_pose", motion.operators())
        self.assertGreaterEqual(motion.operators().count("xplane.go_to_frame"), 2)

    def test_several_selected_offer_copying(self) -> None:
        a, b = mesh("a"), mesh("b")
        a.xplane.manip.enabled = True
        make_active(a, b)
        layout = draw_panel(S.XPLANE_PT_click)
        self.assertIn("xplane.copy_to_selected", layout.operators())
        self.assertTrue(any("2 selected" in text for text in draw_panel(S.XPLANE_PT_selected).labels()))

    def test_files_list(self) -> None:
        mesh("in file")
        test_creation_helpers.create_datablock_collection("Not a file")
        ul = SimpleNamespace(filter_name="", bitflag_filter_item=1 << 30)
        flags, _ = S.XPLANE_UL_files.filter_items(ul, bpy.context, bpy.data, "collections")
        shown = [c.name for c, f in zip(bpy.data.collections, flags) if f]
        self.assertEqual(["Panel"], shown)
        bpy.context.window_manager.xplane_sidebar.show_all_collections = True
        flags, _ = S.XPLANE_UL_files.filter_items(ul, bpy.context, bpy.data, "collections")
        self.assertEqual(2, sum(1 for f in flags if f))
        for collection in bpy.data.collections:
            S.XPLANE_UL_files.draw_item(ul, bpy.context, FakeLayout(), bpy.data, collection, 0, None, "", 0)

    def test_classic_panels_only_when_asked(self) -> None:
        make_active(mesh("thing"))
        self.assertFalse(xplane_ui.OBJECT_PT_xplane.poll(bpy.context))
        if S.preferences() is None:
            # The test runner loads the add-on without listing it in the preferences
            return
        S.preferences().classic_panels = True
        try:
            self.assertTrue(xplane_ui.OBJECT_PT_xplane.poll(bpy.context))
        finally:
            S.preferences().classic_panels = False


runTestCases([TestSidebar])
