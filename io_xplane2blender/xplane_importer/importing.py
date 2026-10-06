"""The high level import functions used by the operators and the tests"""
import os
import time
from typing import Optional

import bpy

from .common import ImportOptions, ImportReport
from .obj_builder import BuiltObj, ObjBuilder
from .obj_parser import ObjParseError, parse_obj_file


def import_obj_file(
    path: str,
    options: Optional[ImportOptions] = None,
    report: Optional[ImportReport] = None,
    parent_collection: Optional[bpy.types.Collection] = None,
    name: str = "",
    livery_objects_dir: str = "",
    objects_root: str = "",
    base_matrix=None,
) -> Optional[BuiltObj]:
    """Imports one OBJ. Failures are reported, not raised, so one bad file doesn't stop a whole aircraft"""
    options = options or ImportOptions()
    report = report or ImportReport()
    started = time.time()
    try:
        obj = parse_obj_file(path)
    except (ObjParseError, OSError) as e:
        report.files_failed += 1
        report.error(f"{os.path.basename(path)}: {e}")
        return None
    builder = ObjBuilder(obj, options, report, parent_collection, name, livery_objects_dir, objects_root, base_matrix)
    try:
        built = builder.build()
    except Exception as e:  # noqa: BLE001 - never lose the rest of an aircraft to one object
        report.files_failed += 1
        report.error(f"{os.path.basename(path)}: import failed ({e.__class__.__name__}: {e})")
        return None
    bpy.context.view_layer.update()
    report.info(f"{os.path.basename(path)}: {time.time() - started:.1f}s")
    return built
