"""Finds an OBJ's texture files, next to it, in its aircraft's folders or in a livery"""

import os
from typing import Dict, Optional

_EXTENSIONS = (".dds", ".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff")


def _unsupported_dds(path: str) -> bool:
    """True for DDS files in a format Blender cannot decode. Only DXT1, DXT3 and DXT5 and plain RGBA are safe"""
    if not path.lower().endswith(".dds"):
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(148)
    except OSError:
        return False
    # "DX10" in the pixel format's FourCC means the real format is in an extra header, BC7 and friends
    return header[:4] == b"DDS " and header[84:88] == b"DX10"


class TextureResolver:
    """Resolves an OBJ's texture paths on disk. A livery's replacement textures are checked first"""

    def __init__(
        self, obj_dir: str, livery_objects_dir: str = "", objects_root: str = ""
    ) -> None:
        self.obj_dir = obj_dir
        # liveries/<name>/objects replaces files of the aircraft's objects folder with the same relative path
        self.livery_objects_dir = livery_objects_dir
        self.objects_root = objects_root
        self._listing: Dict[str, Dict[str, str]] = {}

    def _find_in_dir(self, directory: str, name: str) -> Optional[str]:
        """Case insensitive lookup of `name`, which may have subfolders, inside directory"""
        current = directory
        parts = [
            p
            for p in name.replace("\\", "/").replace(":", "/").split("/")
            if p and p != "."
        ]
        for part in parts:
            if part == "..":
                current = os.path.dirname(current)
                continue
            if current not in self._listing:
                try:
                    self._listing[current] = {e.lower(): e for e in os.listdir(current)}
                except OSError:
                    return None
            entry = self._listing[current].get(part.lower())
            if entry is None:
                return None
            current = os.path.join(current, entry)
        return current if os.path.isfile(current) else None

    def resolve(self, texture_path: str) -> Optional[str]:
        if not texture_path or texture_path.lower() == "none":
            return None
        stem, extension = os.path.splitext(texture_path)
        candidates = [texture_path]
        if extension.lower() in _EXTENSIONS or not extension:
            candidates += [stem + e for e in _EXTENSIONS if e != extension.lower()]
        for candidate in candidates:
            if os.path.isabs(candidate) and os.path.isfile(candidate):
                return candidate
            base = self._find_in_dir(self.obj_dir, candidate)
            if base:
                return self._livery_override(base) or base
        return None

    def reference(self, texture_path: str) -> Optional[str]:
        """
        The file the OBJ names, for the export settings: in the aircraft's folder (not a livery's) and with the
        extension written in the OBJ. X-Plane loads A330_wings.dds for a TEXTURE A330_wings.png, so resolve() loads
        the .dds while the export keeps naming the .png
        """
        if not texture_path or texture_path.lower() == "none":
            return None
        stem, extension = os.path.splitext(texture_path)
        candidates = [texture_path]
        if extension.lower() in _EXTENSIONS or not extension:
            candidates += [stem + e for e in _EXTENSIONS if e != extension.lower()]
        for candidate in candidates:
            found = (
                candidate
                if os.path.isabs(candidate) and os.path.isfile(candidate)
                else self._find_in_dir(self.obj_dir, candidate)
            )
            if found:
                name = os.path.basename(
                    texture_path.replace("\\", "/").replace(":", "/")
                )
                return os.path.join(os.path.dirname(found), name)
        # Not shipped (Laminar's Aerolite pedals name a normal map that is not there): still named, as the OBJ does
        return os.path.normpath(
            os.path.join(
                self.obj_dir, texture_path.replace("\\", "/").replace(":", "/")
            )
        )

    def _livery_override(self, base: str) -> Optional[str]:
        if not (self.livery_objects_dir and self.objects_root):
            return None
        try:
            relative = os.path.relpath(base, self.objects_root)
        except ValueError:
            return None
        if relative.startswith(".."):
            return None
        stem, extension = os.path.splitext(relative)
        for candidate in [relative] + [
            stem + e for e in _EXTENSIONS if e != extension.lower()
        ]:
            found = self._find_in_dir(self.livery_objects_dir, candidate)
            if found:
                return found
        return None
