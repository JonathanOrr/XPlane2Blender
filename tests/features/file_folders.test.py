"""
Where files are exported: a Folder below the .blend file and a Name, and the Scene tab's list grouped by folder,
where a folder ticks, unticks or renames every file in it
"""

import os
from pathlib import Path

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.fake_layout import FakeLayout
from io_xplane2blender.ui import file_tree


def make_file(collection_name: str, saved_as: str, ticked: bool = True) -> bpy.types.Collection:
    collection = test_creation_helpers.create_datablock_collection(collection_name)
    test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", f"{collection_name} mesh", collection=collection_name)
    )
    collection.xplane.is_exportable_collection = ticked
    collection.xplane.layer.name = saved_as
    return collection


class TestFileFolders(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()
        bpy.context.window_manager.xplane_panels.open_folders = ""
        bpy.context.window_manager.xplane_panels.file_filter = ""

    def test_folder_and_name_are_the_two_halves_of_saved_as(self) -> None:
        layer = make_file("Panel", "objects/cockpit/panel").xplane.layer

        self.assertEqual(("objects/cockpit", "panel"), (layer.export_folder, layer.export_stem))
        layer.export_folder = "//objects/gear/"
        self.assertEqual("objects/gear/panel", layer.name)
        layer.export_stem = "knob.obj"
        self.assertEqual("objects/gear/knob", layer.name)
        layer.export_folder = ""
        self.assertEqual("knob", layer.name)

    def test_a_picked_folder_is_made_relative_to_the_blend_file(self) -> None:
        tmp = Path(get_tmp_folder()) / "file_folders"
        tmp.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(tmp / "file_folders.blend"))
        layer = make_file("Panel", "").xplane.layer

        layer.export_folder = str(tmp / "objects" / "cockpit") + os.sep

        # A file without a name yet is named after its collection
        self.assertEqual("objects/cockpit/Panel", layer.name)

    def test_files_are_grouped_by_folder(self) -> None:
        make_file("Panel", "objects/cockpit/panel")
        make_file("Overhead", "objects/cockpit/overhead/overhead")
        make_file("Wing", "objects/wing")
        make_file("Loose", "loose")

        root = file_tree.build(file_tree.listed(bpy.context))

        self.assertEqual(["Loose"], [c.name for c in root.files])
        objects = root.folders["objects"]
        self.assertEqual(["Wing"], [c.name for c in objects.files])
        self.assertEqual(["Panel"], [c.name for c in objects.folders["cockpit"].files])
        self.assertEqual("objects/cockpit/overhead", objects.folders["cockpit"].folders["overhead"].path)
        file_tree.draw(FakeLayout(), bpy.context)

    def test_a_folder_opens_and_closes(self) -> None:
        bpy.ops.xplane.open_folder(folder="objects/cockpit")
        self.assertEqual("objects/cockpit", bpy.context.window_manager.xplane_panels.open_folders)
        bpy.ops.xplane.open_folder(folder="objects/cockpit")
        self.assertEqual("", bpy.context.window_manager.xplane_panels.open_folders)

    def test_ticking_a_folder_ticks_everything_in_it(self) -> None:
        inside = [make_file("Panel", "objects/cockpit/panel", False), make_file("Pedestal", "objects/cockpit/a/b", False)]
        outside = make_file("Wing", "objects/cockpit_extra/wing", False)

        bpy.ops.xplane.tick_folder(folder="objects/cockpit", tick=True)

        self.assertTrue(all(c.xplane.is_exportable_collection for c in inside))
        self.assertFalse(outside.xplane.is_exportable_collection)

    def test_renaming_a_folder_moves_every_file_in_it(self) -> None:
        panel = make_file("Panel", "objects/cockpit/panel")
        pedestal = make_file("Pedestal", "objects/cockpit/center/pedestal")
        wing = make_file("Wing", "objects/wing")

        bpy.ops.xplane.rename_folder(folder="objects/cockpit", new_folder="objects/flightdeck")

        self.assertEqual("objects/flightdeck/panel", panel.xplane.layer.name)
        self.assertEqual("objects/flightdeck/center/pedestal", pedestal.xplane.layer.name)
        self.assertEqual("objects/wing", wing.xplane.layer.name)
        bpy.ops.xplane.rename_folder(folder="objects/flightdeck", new_folder="")
        self.assertEqual("center/pedestal", pedestal.xplane.layer.name)

    def test_export_writes_into_the_folder(self) -> None:
        tmp = Path(get_tmp_folder()) / "file_folders_export"
        tmp.mkdir(parents=True, exist_ok=True)
        make_file("Panel", "objects/cockpit/panel")
        bpy.ops.wm.save_as_mainfile(filepath=str(tmp / "export.blend"))

        bpy.ops.export.xplane_obj(filepath=".", export_is_relative=True)

        self.assertTrue((tmp / "objects" / "cockpit" / "panel.obj").is_file())


runTestCases([TestFileFolders])
