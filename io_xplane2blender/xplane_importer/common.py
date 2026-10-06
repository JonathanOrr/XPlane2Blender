"""Options and reporting shared by the importer modules"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ImportOptions:
    # What to bring in
    import_materials: bool = True  # Texture images and shader nodes
    import_animations: bool = True  # Dataref animations and show/hide
    import_manipulators: bool = True
    import_lights: bool = True
    import_attached_objects: bool = True  # Aircraft: the objects listed in the ACF
    # Aircraft: what to skip
    include_not_drawn: bool = (
        False  # Objects the .acf flags as drawn nowhere (flags = 0)
    )
    hide_default_hidden: bool = (
        True  # Hide what X-Plane hides at the default dataref values
    )
    # How to build it
    all_lods: bool = False  # False imports only the first LOD
    merge_materials: bool = True  # One material per unique look instead of per OBJ
    setup_for_export: bool = (
        True  # Turn each OBJ into an XPlane2Blender root collection
    )
    lit_strength: float = (
        0.0  # Emission strength of the _LIT texture, 0 shows the daytime look
    )
    # Where textures come from
    livery: str = ""  # A folder name inside the aircraft's liveries folder
    # Misc
    scale: float = 1.0
    collection_name: str = ""  # Use this instead of the file name


@dataclass
class ImportReport:
    """Everything worth telling the user at the end of an import"""

    infos: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    objects_imported: int = 0
    meshes_imported: int = 0
    triangles_imported: int = 0
    lights_imported: int = 0
    animations_imported: int = 0
    manipulators_imported: int = 0
    files_imported: int = 0
    files_failed: int = 0

    def info(self, message: str) -> None:
        self.infos.append(message)

    def warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def summary(self) -> str:
        parts = [f"{self.files_imported} file(s)"]
        if self.meshes_imported:
            parts.append(
                f"{self.meshes_imported} meshes ({self.triangles_imported:,} triangles)"
            )
        if self.animations_imported:
            parts.append(f"{self.animations_imported} animations")
        if self.manipulators_imported:
            parts.append(f"{self.manipulators_imported} manipulators")
        if self.lights_imported:
            parts.append(f"{self.lights_imported} lights")
        text = "Imported " + ", ".join(parts)
        if self.files_failed:
            text += f"; {self.files_failed} file(s) failed"
        if self.warnings:
            text += f"; {len(self.warnings)} warning(s)"
        return text
