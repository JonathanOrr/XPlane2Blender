"""
Where a file is exported, as two settings: its Folder below the .blend file and its Name. Both read and write the one
saved setting, the layer's name, which may be a path such as objects/cockpit/panel.
"""

import os

import bpy

from .common import RELATIVE_PATH

# Not saved: they read and write the name. Code that copies saved settings skips them
DERIVED = {"export_folder", "export_stem"}


def split(name: str):
    """'objects/cockpit/panel' -> ('objects/cockpit', 'panel')"""
    folder, _, stem = name.strip().replace("\\", "/").rpartition("/")
    return folder, stem


def join(folder: str, stem: str) -> str:
    return f"{folder}/{stem}" if folder else stem


def clean_folder(value: str) -> str:
    """A folder relative to the .blend file, with / separators, from what was typed or picked"""
    value = value.strip()
    if value.startswith("//"):
        value = value[2:]
    elif os.path.isabs(value) and bpy.data.filepath:
        try:
            value = os.path.relpath(value, os.path.dirname(bpy.data.filepath))
        except ValueError:  # Another drive: the export says what is wrong
            pass
    value = value.replace("\\", "/").strip("/")
    parts = [p for p in value.split("/") if p not in ("", ".")]
    return "/".join(parts)


def _owner_name(layer) -> str:
    return layer.id_data.name if layer.id_data is not None else ""


def get_folder(self) -> str:
    return split(self.name)[0]


def set_folder(self, value: str) -> None:
    self.name = join(clean_folder(value), split(self.name)[1] or _owner_name(self))


def get_stem(self) -> str:
    """A file not named yet is exported under its collection's name"""
    return split(self.name)[1] or _owner_name(self)


def set_stem(self, value: str) -> None:
    stem = value.strip().replace("\\", "/").rpartition("/")[2]
    if stem.lower().endswith(".obj"):
        stem = stem[:-4]
    self.name = join(split(self.name)[0], stem)


def props() -> dict:
    return {
        "export_folder": bpy.props.StringProperty(
            name="Folder",
            description="The folder the OBJ is written to, below the .blend file's folder, such as objects/cockpit."
            " Empty writes it next to the .blend file",
            subtype="DIR_PATH",
            options=RELATIVE_PATH,
            get=get_folder,
            set=set_folder,
        ),
        "export_stem": bpy.props.StringProperty(
            name="Name",
            description="The OBJ's file name, without .obj",
            get=get_stem,
            set=set_stem,
        ),
    }
