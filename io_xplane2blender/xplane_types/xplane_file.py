"""
This is the entry point for the exporter's collection and where it starts writing, proper.
The important paths are

createFilesFromBlenderRootObjects # Iterates through objects and collections to find
|_createFileFromBlenderRootObject
    |_xplane_file.create_xplane_bone_hierarchy # Exporter begins and runs the recursion down the Blender hierarchy
        |_ _recurse # The heart of the collection process, which turns Blender Objects into XPlaneObjects

Later, the write process starts with xplane_file.write, and uses the collected data including
the header and XPlaneBone tree contents to a string
"""

from typing import Dict, List, NamedTuple, Optional, Set, Tuple

import bpy

from io_xplane2blender import xplane_helpers, xplane_props
from io_xplane2blender.xplane_types import (
    xplane_material,
    xplane_material_utils,
)

from ..xplane_helpers import (
    PotentialRoot,
    logger,
)
from .xplane_bone import XPlaneBone
from .xplane_commands import XPlaneCommands
from .xplane_file_keyframes import (  # noqa: F401
    _all_keyframe_infos,
    _pre_scan_all_keyframes,
)
from .xplane_file_tree import XPlaneFileTree
from .xplane_header import XPlaneHeader
from .xplane_mesh import XPlaneMesh


class NotExportableRootError(ValueError):
    pass


def createFilesFromBlenderRootObjects(
    scene: bpy.types.Scene,
    view_layer: bpy.types.ViewLayer,
    only_selected_roots: bool = False,
) -> List["XPlaneFile"]:
    """
    Returns a list of all created XPlaneFiles from all valid roots found,
    ignoring any that could not be created.

    view_layer is needed to test exportability
    """
    xplane_files: List["XPlaneFile"] = []

    if only_selected_roots:
        potential_roots = [ob for ob in scene.objects if ob.select_get()]
    else:
        potential_roots = (
            scene.objects[:] + xplane_helpers.get_collections_in_scene(scene)[1:]
        )

    for potential_root in potential_roots:
        try:
            xplane_file = createFileFromBlenderRootObject(potential_root, view_layer)
        except NotExportableRootError as e:
            pass
        else:
            xplane_file.collection_errors = (
                logger.errorCount() - xplane_file.errors_at_start
            )
            xplane_files.append(xplane_file)

    # Without this the cache never gets cleared
    # and no new animations are exported without a restart
    _all_keyframe_infos.clear()

    return xplane_files


def createFileFromBlenderRootObject(
    potential_root: PotentialRoot, view_layer: bpy.types.ViewLayer
) -> "XPlaneFile":
    """
    Creates the starting point for making an OBJ, creates the file and beings
    the collection phase.

    For the purposes of testing if the potential_root is exportable,
    we need a view_layer to test with

    Raises ValueError when exportable_root is not marked as exporter or something
    prevents collection
    """
    if not xplane_helpers.is_exportable_root(potential_root, view_layer):
        raise NotExportableRootError(f"{potential_root.name} is not a root")
    # Errors logged from here on belong to this file; an earlier file's errors must not stop this one
    errors_at_start = logger.errorCount()
    nested_roots: Set[PotentialRoot] = set()

    def find_nested_roots(potential_roots: List[PotentialRoot]):
        nonlocal nested_roots
        if isinstance(potential_root, bpy.types.Collection):
            nested_roots.update(
                o
                for o in potential_root.all_objects
                if xplane_helpers.is_exportable_root(o, view_layer)
            )

        for child in potential_roots:
            if xplane_helpers.is_exportable_root(child, view_layer):
                nested_roots.update({child})
            find_nested_roots(child.children)

    find_nested_roots(potential_root.children)
    if nested_roots:
        names = [f"'{potential_root.name}'"] + [f"'{r.name}'" for r in nested_roots]
        logger.error(
            f"Nested roots found below '{potential_root.name}'. Checkmark only one of these as the Root: {', '.join(names)}"
        )

    # Name change, we're now confirmed exportable!
    exportable_root = potential_root
    layer_props = exportable_root.xplane.layer
    filename = layer_props.name if layer_props.name else exportable_root.name

    xplane_file = XPlaneFile(filename, layer_props)
    xplane_file.errors_at_start = errors_at_start
    xplane_file.create_xplane_bone_hiearchy(exportable_root)
    bpy.context.scene.frame_set(1)
    assert xplane_file.rootBone, "Root Bone was not assigned during __init__ function"
    return xplane_file


class XPlaneFile(XPlaneFileTree):
    """
    Represents the total contents of a .obj file and
    the settings affecting the output
    """

    def __init__(self, filename: str, options: xplane_props.XPlaneLayer) -> None:
        # A mapping of Blender Object names and the XPlaneBones they were turned into
        # these are garunteed to be under the root bone
        self.commands = XPlaneCommands(self)
        self.filename = filename
        self.options = options
        # How many errors the logger had before this file was collected, and how many collecting it added.
        # Only this file's own errors stop it, so one file with a problem never stops the others
        self.errors_at_start = logger.errorCount()
        self.collection_errors = 0

        self.mesh = XPlaneMesh()
        self._bl_obj_name_to_bone: Dict[str, XPlaneBone] = {}

        # Materials to be used for writing the header directives, a list of 2
        self.reference_material: Optional[xplane_material.XPlaneMaterial] = None

        # the root bone: origin for all animations/objects
        # This isn't really a None type, it is created immediately
        # after in create_xplane_bone_hierarchy
        self.rootBone: XPlaneBone = None

        # Header assumes that its xplaneFile is completely formed
        self.header = XPlaneHeader(self)

        # You'll never ever forget to call XPlaneFile, so,
        # we stick this here
        _pre_scan_all_keyframes()

    def validateMaterials(self) -> bool:
        for xplaneObject in self.get_xplane_objects():
            if xplaneObject.type == "MESH" and xplaneObject.material.options:
                material = xplaneObject.material
                for error in xplane_material_utils.validate(
                    material, self.options.export_type
                ):
                    logger.error(
                        f'Material "{material.name}" in object "{xplaneObject.blenderObject.name}" {error}'
                    )

        # Only this file's errors count, an earlier file's errors must not stop this one
        return logger.errorCount() <= self.errors_at_start

    def getMaterials(self) -> List[bpy.types.Material]:
        """
        Returns a list of the materials used in the OBJ, or an empty list if none found
        Must be called after XPlaneFile.collectBlenderObjects
        """

        materials = []
        objects = self.get_xplane_objects()

        for xplaneObject in objects:
            if (
                xplaneObject.type == "MESH"
                and xplaneObject.material
                and xplaneObject.material.options
            ):
                materials.append(xplaneObject.material)

        return materials

    def writeFooter(self):
        return "# Build with Blender %s (build %s). Exported with XPlane2Blender %s" % (
            bpy.app.version_string,
            bpy.app.build_hash,
            xplane_helpers.VerStruct.current(),
        )

    def write(self) -> str:
        """
        Writes the contents of the file to one giant string with \n's,
        to be written to a file or compared in a unit test
        """
        self.mesh.collectXPlaneObjects(self.get_xplane_objects())

        if not self.validateMaterials():
            return ""

        self.reference_material = xplane_material_utils.reference_material(
            self.getMaterials(), self.options.export_type
        )

        # Joined once: the VT and IDX tables are most of a big file, and each += copied all of it
        parts = [self.header.write(), "\n"]
        meshOut = self.mesh.write()
        parts += [meshOut, "\n" if meshOut else ""]
        del meshOut
        lodsOut = self._writeLods()
        parts += [lodsOut, "\n" if lodsOut else "", self.writeFooter()]
        return "".join(parts)

    def _writeLods(self) -> str:
        o = ""
        num_lods = int(self.options.lods)

        if num_lods:
            defined_buckets = self.options.lod[:num_lods]
            # --- ATTR_LOD validations ----------------------------------------
            # LOD spec #2
            if defined_buckets[0].near != 0:
                logger.error(
                    f"{self.filename}'s LOD buckets must start at 0, is {defined_buckets[0].near}"
                )
                return o

            for bucket_number in range(0, int(self.options.lods)):
                near = self.options.lod[bucket_number].near
                far = self.options.lod[bucket_number].far
                # LOD spec #7
                if near == far:
                    logger.error(
                        f"{self.filename}'s LOD bucket #{bucket_number+1}'s Near and Far match: ({near}, {far})"
                    )
                    return o
                # LOD spec #3
                elif near > far:
                    logger.error(
                        f"{self.filename}'s LOD bucket #{bucket_number+1}'s Near is greater than its Far: ({near}, {far})"
                    )

            class LODStruct(NamedTuple):
                near: int
                far: int

                def __repr__(self) -> str:
                    return f"({self.near}, {self.far})"

            # len(selective_pairs) in {0, 2, 4} == True
            # len(additive_pairs) in range(1, 5) == True
            # if len additive_pairs is 1 and len selective_pairs is greater than 2, you are in selective mode
            # if len additive_pairs is > 1 and len selective pairs is greater than 2, you are in mixed modes
            additive_pairs: Tuple[Tuple[int, LODStruct], ...] = tuple(
                [
                    (i, LODStruct(lod.near, lod.far))
                    for i, lod in enumerate(defined_buckets)
                    if i < num_lods and lod.near == 0
                ]
            )

            # To be in selective mode, you must have at least two LOD buckets,
            # (0, m), (m, m+something), where m is meters
            selective_pairs: List[Tuple[int, LODStruct]] = []
            try:
                for i, (prev_lod, next_lod) in enumerate(
                    zip(defined_buckets[: num_lods - 1], defined_buckets[1:])
                ):
                    if prev_lod.far == next_lod.near:
                        if (
                            not selective_pairs
                            or (i - 1, (prev_lod.near, prev_lod.far))
                            != selective_pairs[-1]
                        ):
                            selective_pairs.append(
                                (i, LODStruct(prev_lod.near, prev_lod.far))
                            )
                        selective_pairs.append(
                            (i + 1, LODStruct(next_lod.near, next_lod.far))
                        )
                    # LOD spec #6
                    elif prev_lod.far < next_lod.near:
                        logger.error(
                            f"In {self.filename}, gap found between LOD bucket #{i} and {i+1}. Far and Near should match: ({prev_lod}, {next_lod})"
                        )
                    elif (
                        prev_lod.far > next_lod.near and len(additive_pairs) == 1
                    ):  # every additive pair's far will always be greater than 0, ignore
                        logger.error(
                            f"In {self.filename}, overlap found between LOD bucket #{i} and {i+1}. Far and Near should match: ({prev_lod}, {next_lod})"
                        )
            except IndexError:  # fails when defined_buckets has only 1 bucket
                pass
            selective_pairs = tuple(selective_pairs)
            assert (
                len(selective_pairs) % 2 == 0
            ), f"{selective_pairs} not a multiple of two"

            # LOD spec #5
            # It isn't just having a pairs, they both have to be in meaningful amounts
            # to show mixing
            if len(additive_pairs) > 1 and len(selective_pairs) >= 2:
                logger.error(
                    f"{self.filename} uses Additive and Selective LODs modes. Choose only one: {[str(lod) for lod in defined_buckets]}"
                )

            # LOD spec #3 (Additive version)
            # additive_pairs and selective_pairs will always share a first
            # but never a second pair - avoids false positives
            if len(additive_pairs) > 1 and any(
                [
                    not prev_lod.far < next_lod.far
                    for (prev_index, (prev_lod)), (next_index, (next_lod)) in zip(
                        additive_pairs[:-1], additive_pairs[1:]
                    )
                ]
            ):
                logger.error(
                    f"{self.filename}'s LOD buckets' Far values must be in ascending order: {[(lod) for i, lod in additive_pairs]}"
                )
            # -----------------------------------------------------------------
            # LOD spec #1, this is written before the first ever
            # or subsequent calls to commands.write
            initial_written = self.commands.written.copy()
            for lod_bucket_index, lod_bucket in enumerate(defined_buckets):
                # LOD state is independent, including defaults set by GLOBAL_*.
                self.commands.written = initial_written.copy()
                o += f"ATTR_LOD\t{lod_bucket.near}\t{lod_bucket.far}\n"
                o += self.commands.write(lod_bucket_index=lod_bucket_index)
        else:
            o += self.commands.write(lod_bucket_index=None)

        # print(o)
        return o
