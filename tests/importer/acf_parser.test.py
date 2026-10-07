import os

import bpy

from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import (
    TempFolder,
    obj_text,
    write_file,
    write_png,
)
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.acf_parser import (
    AcfParseError,
    parse_acf_file,
    resolve_object_path,
)
from io_xplane2blender.xplane_importer.aircraft import import_aircraft
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport


def acf_text(objects: dict, extra: str = "", version: int = 1200) -> str:
    """objects maps an index to a dict of the _obja fields"""
    lines = [f"I\n{version} Version\nACF\n\nPROPERTIES_BEGIN"]
    lines.append("P acf/_descrip Test Plane")
    lines.append(extra) if extra else None
    for index, fields in objects.items():
        for key, value in fields.items():
            lines.append(f"P _obja/{index}/{key} {value}")
    lines.append("PROPERTIES_END\n")
    return "\n".join(lines)


def entry(file: str, flags: int = 1033, x=0.0, y=0.0, z=0.0, body=-1, wing=-1, gear=-1, hide="") -> dict:
    fields = {
        "_obj_flags": flags,
        "_v10_att_body": body,
        "_v10_att_file_stl": file,
        "_v10_att_gear": gear,
        "_v10_att_phi_ref": "0.0",
        "_v10_att_psi_ref": "0.0",
        "_v10_att_the_ref": "0.0",
        "_v10_att_wing": wing,
        "_v10_att_x_acf_prt_ref": x,
        "_v10_att_y_acf_prt_ref": y,
        "_v10_att_z_acf_prt_ref": z,
    }
    if hide:
        fields["_obj_hide_dataref"] = hide
    return fields


class TestAcfParser(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.folder = TempFolder()

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def test_objects_are_read(self) -> None:
        text = acf_text(
            {0: entry("../cockpit.obj", 6157, x=10.0, y=-5.0, z=2.5), 1: entry("wing.obj", 528, wing=3, hide="sim/dr[22]")}
        )
        acf = parse_acf_file(write_file(self.folder.join("Plane.acf"), text))
        self.assertEqual((acf.version, acf.name), (1200, "Test Plane"))
        first, second = acf.objects
        self.assertEqual((first.file, first.flags), ("../cockpit.obj", 6157))
        # Feet to meters, X-Plane's axes
        self.assertEqual(tuple(round(v, 4) for v in first.position), (3.048, -1.524, 0.762))
        self.assertFalse(first.is_attached)
        self.assertTrue(second.is_attached and second.is_damage)
        self.assertEqual((second.attached_wing, second.hide_dataref), (3, "sim/dr[22]"))

    def test_entries_without_a_file_are_ignored(self) -> None:
        text = acf_text({0: entry("a.obj"), 1: {"_obj_flags": 1}})
        acf = parse_acf_file(write_file(self.folder.join("Plane.acf"), text))
        self.assertEqual(len(acf.objects), 1)

    def test_old_binary_files_are_refused(self) -> None:
        path = write_file(self.folder.join("Old.acf"), "I\n800 version\nACF\n")
        with self.assertRaises(AcfParseError):
            parse_acf_file(path)

    def test_object_paths_ignore_case_and_use_the_objects_folder(self) -> None:
        write_file(self.folder.join("Objects", "Sub", "Wing.OBJ"), obj_text(""))
        write_file(self.folder.join("Cockpit.obj"), obj_text(""))
        acf = parse_acf_file(write_file(self.folder.join("Plane.acf"), acf_text({0: entry("sub/wing.obj"), 1: entry("../cockpit.obj"), 2: entry("missing.obj")})))
        found = [resolve_object_path(acf, o) for o in acf.objects]
        self.assertTrue(found[0].endswith(os.path.join("Objects", "Sub", "Wing.OBJ")))
        self.assertTrue(found[1].endswith("Cockpit.obj"))
        self.assertIsNone(found[2])

    def test_liveries_are_listed(self) -> None:
        acf = parse_acf_file(write_file(self.folder.join("Plane.acf"), acf_text({0: entry("a.obj")})))
        self.assertEqual(acf.liveries(), [])
        os.makedirs(self.folder.join("liveries", "Red"))
        os.makedirs(self.folder.join("liveries", "Blue"))
        write_file(self.folder.join("liveries", "readme.txt"), "x")
        self.assertEqual(acf.liveries(), ["Blue", "Red"])


runTestCases([TestAcfParser])
