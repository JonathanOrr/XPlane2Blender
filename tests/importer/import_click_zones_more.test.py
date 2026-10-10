"""
Click zones the importer used to drop or simplify: touch screens (ATTR_manip_device, X-Plane 12.1), wrap buttons
(the C172's OAT button) and no-op zones with Laminar's dataref label
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.tests.importer_helpers import TempFolder, obj_text, write_file, write_png
from io_xplane2blender.tests.roundtrip_helpers import HOUSE_IDX, HOUSE_VT
from io_xplane2blender.xplane_helpers import logger, unfinished
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file


def manip_lines(text: str):
    return [" ".join(line.split()) for line in text.splitlines() if line.split()[:1] and line.split()[0].startswith("ATTR_manip_")]


class TestImportClickZonesMore(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        test_creation_helpers.create_initial_test_setup()
        unfinished.clear()
        self.folder = TempFolder()
        write_png(self.folder.join("tex.png"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def import_zone(self, line: str):
        text = obj_text(f"{line}\nTRIS 0 12\n", header="TEXTURE tex.png\n", vertices=HOUSE_VT, indices=HOUSE_IDX, tris=None)
        report = ImportReport()
        built = import_obj_file(write_file(self.folder.join("part.obj"), text), ImportOptions(make_exportable=True), report)
        built.collection.xplane.layer.name = self.folder.join("part")
        part = next(o for o in built.collection.all_objects if o.type == "MESH")
        return built, part, report

    def round_trip(self, line: str):
        built, part, report = self.import_zone(line)
        exported = self.exportExportableRoot(built.collection)
        self.assertLoggerErrors(0)
        self.assertEqual([], report.warnings)
        return part, manip_lines(exported)

    def test_a_touch_screen_of_an_x_plane_device(self) -> None:
        part, lines = self.round_trip("ATTR_manip_device hand G1000_PFD1 PFD touch")
        manip = part.xplane.manip
        self.assertEqual((True, C.MANIP_DEVICE, C.DEVICE_G1000_PFD1), (manip.enabled, manip.type, manip.device_name))
        self.assertEqual(["ATTR_manip_device hand G1000_PFD1 PFD touch"], lines)
        self.assertEqual("Touch screen", I.control_kind(manip).label)
        self.assertEqual(["device_name"], [f.prop for f in I.manip_fields(manip)])

    def test_a_touch_screen_of_a_plugin_device(self) -> None:
        part, lines = self.round_trip("ATTR_manip_device button my_efb Touch the EFB")
        manip = part.xplane.manip
        self.assertEqual((C.DEVICE_PLUGIN, "my_efb"), (manip.device_name, manip.plugin_device))
        self.assertEqual(["ATTR_manip_device button my_efb Touch the EFB"], lines)
        self.assertEqual(["device_name", "plugin_device"], [f.prop for f in I.manip_fields(manip)])

    def test_a_plugin_touch_screen_without_its_id_is_unfinished_work(self) -> None:
        built, part, _ = self.import_zone("ATTR_manip_device button my_efb Touch")
        part.xplane.manip.plugin_device = ""
        self.assertIn("Clickable: no device id yet", I.problems(part, bpy.context.scene))

        exported = self.exportExportableRoot(built.collection)

        self.assertEqual([], [l for l in manip_lines(exported) if l.startswith("ATTR_manip_device")])
        self.assertFalse(logger.hasErrors())
        self.assertEqual([part.name], unfinished.items["touch screens without a device ID (not clickable)"])

    def test_a_wrap_button(self) -> None:
        # The C172's OAT button: one click steps C, F, volts and back to C
        part, lines = self.round_trip(
            "ATTR_manip_wrap button 1 0 -1 2 laminar/c172/knob_OAT Toggle from OAT C°, F° and battery voltage"
        )
        manip = part.xplane.manip
        self.assertEqual((C.MANIP_WRAP, 1.0, -1.0, 2.0), (manip.type, manip.v_down, manip.v1_min, manip.v1_max))
        self.assertEqual(
            ["ATTR_manip_wrap button 1.000 0.000 -1.000 2.000 laminar/c172/knob_OAT Toggle from OAT C°, F° and battery voltage"],
            lines,
        )

    def test_a_no_op_keeps_laminars_dataref_label(self) -> None:
        part, lines = self.round_trip("ATTR_manip_noop sim/cockpit2/gauges/indicators/airspeed_kts_pilot")
        self.assertEqual("sim/cockpit2/gauges/indicators/airspeed_kts_pilot", part.xplane.manip.noop_label)
        self.assertEqual(["ATTR_manip_noop sim/cockpit2/gauges/indicators/airspeed_kts_pilot"], lines)

    def test_a_plain_no_op_stays_plain_and_is_finished(self) -> None:
        part, lines = self.round_trip("ATTR_manip_noop")
        self.assertEqual(["ATTR_manip_noop"], lines)
        self.assertFalse([p for p in I.problems(part, bpy.context.scene) if p.startswith("Clickable")])

    def test_a_hash_in_a_tooltip_is_text(self) -> None:
        # The 737's "Autothrottle Disconnect #1" and the Lancair's "Door #2 Handle"
        part, lines = self.round_trip("ATTR_manip_command button sim/door_2 Door #2 Handle")
        self.assertEqual("Door #2 Handle", part.xplane.manip.tooltip)
        self.assertEqual(["ATTR_manip_command button sim/door_2 Door #2 Handle"], lines)

    def test_a_click_zone_without_a_command_is_left_out(self) -> None:
        # Laminar's PA-18 has a click zone whose values are commented out; a new button has no command yet either.
        # Written, the tooltip's first word would be read as the command
        built, part, _ = self.import_zone("ATTR_manip_command  ################## ANIM_keyframe_loop 100")
        part.xplane.manip.tooltip = "Not done yet"

        exported = self.exportExportableRoot(built.collection)

        self.assertEqual([], manip_lines(exported))
        self.assertFalse(logger.hasErrors())
        self.assertEqual([part.name], unfinished.items["click zones without a command (not clickable)"])
        self.assertIn("Clickable: no command yet", I.problems(part, bpy.context.scene))


runTestCases([TestImportClickZonesMore])
