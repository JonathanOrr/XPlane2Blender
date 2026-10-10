"""Imports a whole aircraft: every object an .acf lists, placed and textured as X-Plane would show it"""

import math
import os
from typing import Callable, Optional

import bpy
import mathutils

from . import frames
from . import transforms as T
from .acf_parser import (
    AcfFile,
    AcfObject,
    AcfParseError,
    _child_folder,
    parse_acf_file,
    resolve_object_path,
)
from .common import ImportOptions, ImportReport
from .importing import import_obj_file


def _placement_matrix(item: AcfObject) -> mathutils.Matrix:
    """X-Plane space matrix that moves an object to where the .acf puts it"""
    phi, psi, theta = item.rotation
    matrix = mathutils.Matrix.Translation(item.position)
    if psi:
        # Heading is clockwise seen from above, a rotation about the up axis
        matrix = matrix @ T.rotation_xp((0, 1, 0), -psi)
    if theta:
        matrix = matrix @ T.rotation_xp((1, 0, 0), theta)
    if phi:
        matrix = matrix @ T.rotation_xp((0, 0, 1), -phi)
    return matrix


def import_aircraft(
    acf_path: str,
    options: Optional[ImportOptions] = None,
    report: Optional[ImportReport] = None,
    livery: str = "",
    include_damage: bool = False,
    include_attached: bool = False,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Optional[bpy.types.Collection]:
    options = options or ImportOptions()
    report = report or ImportReport()
    try:
        acf: AcfFile = parse_acf_file(acf_path)
    except AcfParseError as e:
        report.error(str(e))
        return None

    root = bpy.data.collections.new(acf.name)
    bpy.context.scene.collection.children.link(root)
    root["xplane_acf"] = acf_path
    root["xplane_acf_version"] = acf.version

    livery_objects = ""
    if livery:
        candidate = _child_folder(
            os.path.join(_child_folder(acf.folder, "liveries"), livery), "objects"
        )
        if os.path.isdir(candidate):
            livery_objects = candidate
        else:
            report.warn(
                f"Livery '{livery}' has no objects folder, the default textures are used"
            )

    skipped_damage = skipped_attached = 0
    prefill_only = []
    for number, item in enumerate(acf.objects):
        if progress is not None:
            progress(number, len(acf.objects))
        if item.is_damage and not include_damage:
            skipped_damage += 1
            continue
        if item.is_attached and not include_attached and not item.is_damage:
            skipped_attached += 1
            continue
        path = resolve_object_path(acf, item)
        if path is None:
            report.error(
                f"{item.file}: the file was not found (listed in {os.path.basename(acf_path)})"
            )
            report.files_failed += 1
            continue
        stem = os.path.splitext(os.path.basename(path))[0]
        built = import_obj_file(
            path,
            options,
            report,
            parent_collection=root,
            name=stem,
            livery_objects_dir=livery_objects,
            objects_root=acf.objects_folder,
            base_matrix=_placement_matrix(item),
            update_view_layer=False,
            settle_frames=False,
        )
        if built is not None:
            built.collection["xplane_acf_object"] = item.index
            built.collection["xplane_obj_flags"] = item.flags
            if item.hide_dataref:
                built.collection["xplane_hide_dataref"] = item.hide_dataref
            if item.is_glass:
                built.collection["xplane_glass"] = True
            if item.is_prefill_only:
                # Still exported (the OBJ is named by the file settings, not the collection), but named for what it is
                built.collection.name = f"{stem} (prefill only, not drawn)"
                prefill_only.append(stem)
    if prefill_only:
        report.info(
            f"Prefill Only, never drawn by X-Plane (it hides the clouds behind it): {', '.join(prefill_only)}"
        )
    if skipped_damage:
        report.info(
            f"{skipped_damage} damage object(s) were skipped (they only show when a part breaks)"
        )
    if skipped_attached:
        report.info(
            f"{skipped_attached} object(s) attached to wings, gear or the body were skipped"
        )
    frames.settle(root.all_objects, bpy.context.scene)
    bpy.context.view_layer.update()
    return root
