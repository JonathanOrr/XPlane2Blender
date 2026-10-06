"""A parser for X-Plane aircraft files (.acf, the text format of X-Plane 10, 11 and 12). No Blender needed"""
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

FEET_TO_METERS = 0.3048

_OBJA = re.compile(r"_obja/(\d+)/(\S+)$")


class AcfParseError(Exception):
    pass


@dataclass
class AcfObject:
    index: int
    file: str  # As written in the .acf, relative to the aircraft's "objects" folder
    flags: int = 0
    # Position of the object's origin relative to the aircraft's origin, in meters, X-Plane axes (x right, y up, z back)
    position: tuple = (0.0, 0.0, 0.0)
    # Heading, pitch and roll in degrees, ordered (phi, psi, the) like the file does
    rotation: tuple = (0.0, 0.0, 0.0)
    attached_body: int = -1
    attached_wing: int = -1
    attached_gear: int = -1
    hide_dataref: str = ""
    raw: Dict[str, str] = field(default_factory=dict)

    @property
    def is_attached(self) -> bool:
        """Attached to a wing, body or gear part. Those objects move with that part (or only show on damage)"""
        return self.attached_body >= 0 or self.attached_wing >= 0 or self.attached_gear >= 0

    @property
    def is_damage(self) -> bool:
        return bool(self.flags & 512)

    @property
    def is_glass(self) -> bool:
        return bool(self.flags & 2 or self.flags & 8192)


@dataclass
class AcfFile:
    path: str
    version: int
    properties: Dict[str, str] = field(default_factory=dict)
    objects: List[AcfObject] = field(default_factory=list)

    @property
    def folder(self) -> str:
        return os.path.dirname(self.path)

    @property
    def objects_folder(self) -> str:
        return os.path.join(self.folder, "objects")

    @property
    def name(self) -> str:
        """A human friendly name for the aircraft"""
        for key in ("acf/_descrip", "acf/_name"):
            value = self.properties.get(key, "").strip()
            if value:
                return value
        return os.path.splitext(os.path.basename(self.path))[0]

    def liveries(self) -> List[str]:
        folder = os.path.join(self.folder, "liveries")
        try:
            return sorted(
                e for e in os.listdir(folder) if os.path.isdir(os.path.join(folder, e))
            )
        except OSError:
            return []


def _float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_acf_file(path: str) -> AcfFile:
    try:
        with open(path, "rb") as f:
            text = f.read().decode("latin-1")
    except OSError as e:
        raise AcfParseError(f"Could not read {os.path.basename(path)}: {e}")
    lines = text.splitlines()
    version = 0
    for line in lines[:5]:
        match = re.match(r"\s*(\d+)\s+[Vv]ersion", line)
        if match:
            version = int(match.group(1))
            break
    if version < 1000:
        raise AcfParseError(
            f"{os.path.basename(path)} is not a text based .acf from X-Plane 10 or newer "
            "(older binary aircraft files are not supported)"
        )

    acf = AcfFile(path, version)
    objects: Dict[int, Dict[str, str]] = {}
    for line in lines:
        if not line.startswith("P "):
            continue
        key, _, value = line[2:].partition(" ")
        match = _OBJA.match(key)
        if match:
            objects.setdefault(int(match.group(1)), {})[match.group(2)] = value.strip()
        else:
            acf.properties[key] = value.strip()

    for index in sorted(objects):
        raw = objects[index]
        file = raw.get("_v10_att_file_stl", "").strip()
        if not file:
            continue
        acf.objects.append(
            AcfObject(
                index=index,
                file=file,
                flags=_int(raw.get("_obj_flags", "0")),
                position=tuple(
                    _float(raw.get(f"_v10_att_{axis}_acf_prt_ref")) * FEET_TO_METERS for axis in ("x", "y", "z")
                ),
                rotation=(
                    _float(raw.get("_v10_att_phi_ref")),
                    _float(raw.get("_v10_att_psi_ref")),
                    _float(raw.get("_v10_att_the_ref")),
                ),
                attached_body=_int(raw.get("_v10_att_body", "-1"), -1),
                attached_wing=_int(raw.get("_v10_att_wing", "-1"), -1),
                attached_gear=_int(raw.get("_v10_att_gear", "-1"), -1),
                hide_dataref=raw.get("_obj_hide_dataref", ""),
                raw=raw,
            )
        )
    return acf


def resolve_object_path(acf: AcfFile, obj: AcfObject) -> Optional[str]:
    """Finds the object's file. Names are relative to the aircraft's objects folder and may be case-insensitive"""
    name = obj.file.replace("\\", "/")
    for base in (acf.objects_folder, acf.folder):
        current = base
        found = True
        for part in [p for p in name.split("/") if p and p != "."]:
            if part == "..":
                current = os.path.dirname(current)
                continue
            try:
                entries = {e.lower(): e for e in os.listdir(current)}
            except OSError:
                found = False
                break
            entry = entries.get(part.lower())
            if entry is None:
                found = False
                break
            current = os.path.join(current, entry)
        if found and os.path.isfile(current):
            return current
    return None
