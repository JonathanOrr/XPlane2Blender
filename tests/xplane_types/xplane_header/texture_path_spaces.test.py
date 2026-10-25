import os
import tempfile

from io_xplane2blender.tests import *
from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_types.xplane_header import XPlaneHeader


class TestTexturePathSpaces(XPlaneTestCase):
    """OBJ8 tokens are whitespace separated, so a space in an emitted path breaks the file"""

    def setUp(self):
        super().setUp()
        self._export_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._export_dir.cleanup()
        super().tearDown()

    def _get_path(self, res_path: str) -> str:
        return XPlaneHeader.get_path_relative_to_dir(None, res_path, self._export_dir.name)

    def test_space_in_file_name_is_error(self) -> None:
        with self.assertRaises(ValueError):
            self._get_path("//what ever.png")
        self.assertLoggerErrors(1)

    def test_space_in_directory_is_error(self) -> None:
        with self.assertRaises(ValueError):
            self._get_path("//my textures/tex.png")
        self.assertLoggerErrors(1)

    def test_a_space_on_the_way_to_textures_elsewhere_names_the_folder(self) -> None:
        # An imported aircraft's textures stay in the X-Plane folder: exported elsewhere, the path goes through it
        parent = os.path.dirname(self._export_dir.name)
        with self.assertRaises(ValueError):
            self._get_path(os.path.join(parent, "X-Plane 12", "Aircraft", "objects", "panel.png"))
        (error,) = logger.findErrors()
        self.assertIn("a space in 'X-Plane 12'", error["message"])
        self.assertIn("Export the OBJ into the aircraft folder", error["message"])
        logger.clearMessages()

    def test_no_space_is_silent(self) -> None:
        self.assertEqual(self._get_path("//good_name.png").endswith("good_name.png"), True)
        self.assertLoggerErrors(0)


runTestCases([TestTexturePathSpaces])
