from typing import List, Optional

from ..xplane_constants import (
    COCKPIT_FEATURE_DEVICE,
    COCKPIT_FEATURE_NONE,
    COCKPIT_FEATURE_PANEL,
    EXPORT_TYPE_AIRCRAFT,
)
from .xplane_material import XPlaneMaterial


def _panel_errors(mat: XPlaneMaterial) -> List[str]:
    errors = []
    if mat.options.lightLevel:
        errors.append("Must not override light level.")
    if mat.options.draw:
        if mat.textureLit:
            errors.append("Must not have a lit/emissive texture.")
        if mat.textureNormal:
            errors.append("Must not have a normal/alpha/specularity texture.")
    if mat.options.cockpit_feature == COCKPIT_FEATURE_NONE:
        errors.append("Must be part of the cockpit panel.")
    if mat.options.surfaceType != "none":
        errors.append('Must have the surface type "none".')
    return errors


def _cockpit_errors(mat: XPlaneMaterial) -> List[str]:
    errors = []
    if mat.options.cockpit_feature == COCKPIT_FEATURE_DEVICE:
        if not any(mat.options.get(f"device_bus_{i}") for i in range(6)):
            errors.append("Cockpit device must specify at least one bus")
    if mat.options.cockpit_feature == COCKPIT_FEATURE_PANEL:
        errors.append("Cockpit .obj Material cannot be 'Part Of Panel'.")
    return errors


def _aircraft_errors(mat: XPlaneMaterial) -> List[str]:
    errors = []
    if mat.options.cockpit_feature == COCKPIT_FEATURE_DEVICE:
        if not any(mat.options.get(f"device_bus_{i}") for i in range(6)):
            errors.append("Cockpit device must specify at least one bus")
    if mat.options.cockpit_feature == COCKPIT_FEATURE_PANEL:
        errors.append("Aircraft .obj Material cannot be 'Part Of Panel'.")
    if mat.options.solid_camera:
        errors.append("Must have camera collision disabled.")
    if mat.blenderObject.xplane.manip.enabled:
        errors.append("Must not be a manipulator.")
    return errors


def validate(mat: XPlaneMaterial, export_type: str) -> List[str]:
    """Returns what is wrong with a material, in words, for an aircraft or cockpit file"""
    if mat.options is None:
        return ["Is invalid."]
    if mat.options.cockpit_feature == COCKPIT_FEATURE_PANEL:
        return _panel_errors(mat)
    if export_type == EXPORT_TYPE_AIRCRAFT:
        return _aircraft_errors(mat)
    if mat.options.cockpit_feature == COCKPIT_FEATURE_NONE:
        return _cockpit_errors(mat)
    return []


def reference_material(materials: List[XPlaneMaterial], export_type: str) -> Optional[XPlaneMaterial]:
    """The first drawn, valid, non-panel material: the one file-wide settings like GLOBAL_specular follow"""
    errors_of = _aircraft_errors if export_type == EXPORT_TYPE_AIRCRAFT else _cockpit_errors
    for mat in materials:
        if mat.options.draw and not errors_of(mat):
            return mat
    return None
