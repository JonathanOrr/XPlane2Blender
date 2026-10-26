"""
An imported aircraft laid out again below the .blend file's folder: the files its OBJs use (textures, decals, rain
and particle files) are copied to the same places relative to the aircraft folder, and each OBJ is exported where it
was. The paths written in the exported OBJs are then the ones the original OBJs had.
"""

import os
import shutil
from typing import Dict, List, Optional

import bpy

from .common import ImportReport
from .textures import _EXTENSIONS


class AircraftCopy:
    def __init__(self, aircraft_dir: str, target_dir: str) -> None:
        self.aircraft_dir = os.path.normpath(aircraft_dir)
        self.target_dir = os.path.normpath(target_dir)
        self.copied = 0
        self.copied_bytes = 0
        # Already there: never overwritten, they may have been edited since
        self.kept = 0
        self.outside: List[str] = []
        self.failed: List[str] = []
        self._done: Dict[str, str] = {}

    def _relative(self, path: str) -> Optional[str]:
        try:
            relative = os.path.relpath(os.path.normpath(path), self.aircraft_dir)
        except ValueError:  # Another drive
            return None
        return None if relative.startswith("..") else relative

    def place(self, path: str) -> str:
        """Where a file of the aircraft goes below the .blend's folder, or the path itself if it is not the aircraft's"""
        relative = self._relative(path)
        if relative is None:
            return path
        return os.path.join(self.target_dir, relative)

    def copy(self, path: str) -> str:
        """Copies a file the OBJs use, with its other formats (X-Plane loads panel.dds for a panel.png), to its place"""
        if path in self._done:
            return self._done[path]
        placed = self.place(path)
        if placed == path:
            if path not in self.outside:
                self.outside.append(path)
        elif os.path.normcase(placed) != os.path.normcase(path):
            for source in _formats_of(path):
                try:
                    self._copy_one(source, os.path.join(os.path.dirname(placed), os.path.basename(source)))
                except OSError as e:
                    self.failed.append(f"{source} ({e.strerror or e})")
        self._done[path] = placed
        return placed

    def _copy_one(self, source: str, target: str) -> None:
        if not os.path.isfile(source):  # Named by the OBJ but not shipped
            return
        if os.path.exists(target):
            self.kept += 1
            return
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copy2(source, target)
        self.copied += 1
        self.copied_bytes += os.path.getsize(target)

    def export_name(self, obj_path: str) -> Optional[str]:
        """objects/cockpit/panel for <aircraft>/objects/cockpit/panel.obj: the file is exported where it was"""
        relative = self._relative(obj_path)
        if relative is None:
            return None
        return os.path.splitext(relative)[0].replace("\\", "/")

    def tell(self, report: ImportReport) -> None:
        if self.copied:
            size = self.copied_bytes / 1024**2
            report.info(f"Copied {self.copied} texture and other file(s) ({size:.0f} MB) next to the .blend file")
        if self.kept:
            report.info(f"{self.kept} file(s) were next to the .blend file already and were kept as they are")
        for failure in self.failed:
            report.warn(f"Could not copy {failure}")
        for path in self.outside:
            report.warn(f"{path} is not in the aircraft's folder, it was used where it is and not copied")


def _formats_of(path: str) -> List[str]:
    """The file and its siblings with the same name in other image formats"""
    folder, name = os.path.split(path)
    stem, extension = os.path.splitext(name)
    if extension.lower() not in _EXTENSIONS:
        return [path]
    try:
        entries = os.listdir(folder)
    except OSError:
        return [path]
    return [
        os.path.join(folder, e)
        for e in entries
        if os.path.splitext(e)[0].lower() == stem.lower() and os.path.splitext(e)[1].lower() in _EXTENSIONS
    ] or [path]


def blend_relative(path: str) -> str:
    """//objects/textures/panel.png when the file is below the .blend's folder, so the project can be moved"""
    if not bpy.data.filepath:
        return path
    try:
        relative = bpy.path.relpath(path)
    except ValueError:
        return path
    return path if relative.startswith("//..") else relative
