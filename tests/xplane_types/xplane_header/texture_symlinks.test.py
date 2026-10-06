import os
import tempfile
from pathlib import Path

import bpy

from io_xplane2blender.tests import XPlaneTestCase, runTestCases, test_creation_helpers


class TestTextureSymlinks(XPlaneTestCase):
    def _check_texture_paths(self, saved: bool) -> None:
        bpy.ops.wm.read_homefile(use_empty=True)
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "proj"
            project.mkdir()
            real = Path(tmp) / "real"
            real.mkdir()
            (real / "tex.png").touch()
            try:
                (project / "link.png").symlink_to("../real/tex.png")
                (project / "textures").symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"Symlinks unavailable: {exc}")

            if saved:
                bpy.ops.wm.save_as_mainfile(filepath=str(project / "scene.blend"))
            root = test_creation_helpers.create_datablock_collection("Textures")
            old_cwd = os.getcwd()
            try:
                os.chdir(project)
                for path, expected in (
                    ("//link.png", "link.png"),
                    ("./link.png", "link.png"),
                    (str(project / "link.png"), "link.png"),
                    ("../proj/link.png", "link.png"),
                    ("//textures/tex.png", "textures/tex.png"),
                ):
                    with self.subTest(path=path, saved=saved):
                        root.xplane.layer.texture = path
                        xp_file = self.createXPlaneFileFromPotentialRoot(root)
                        xp_file.filename = str(project / "export.obj")
                        out = xp_file.write()
                        textures = [
                            line.split()[1]
                            for line in out.splitlines()
                            if line.split()[:1] == ["TEXTURE"]
                        ]
                        self.assertEqual([expected], textures)
                        self.assertLoggerErrors(0)
            finally:
                os.chdir(old_cwd)

    def test_saved_blend_preserves_texture_symlinks(self) -> None:
        self._check_texture_paths(saved=True)

    def test_unsaved_blend_preserves_texture_symlinks(self) -> None:
        self._check_texture_paths(saved=False)


runTestCases([TestTextureSymlinks])
