import array
import collections
import re
import time
from typing import List, Optional

import bpy
import mathutils
import numpy as np

from io_xplane2blender import xplane_helpers

from ..xplane_config import getDebug
from ..xplane_constants import *
from ..xplane_helpers import floatToStr, logger
from .xplane_face import XPlaneFace
from .xplane_object import XPlaneObject

# Normals closer than this are one vertex: Blender stores custom normals with about 1e-5 of error, so the same
# normal on two faces of a vertex comes back a little different and would be written twice (imported meshes)
NORMAL_MERGE = 1e-4


def _turned_corner_normals(mesh, matrix) -> np.ndarray:
    """The mesh's corner normals as they point once the mesh is transformed by matrix"""
    normals = np.empty(len(mesh.loops) * 3, dtype=np.float64)
    if hasattr(mesh, "calc_normals_split"):  # Blender before 4.1 (its corner_normals is empty)
        mesh.calc_normals_split()
        mesh.loops.foreach_get("normal", normals)
    else:
        mesh.corner_normals.foreach_get("vector", normals)
    turn = np.array(matrix.to_3x3().inverted_safe().transposed())
    normals = normals.reshape(-1, 3) @ turn.T
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths < 1e-12] = 1.0
    return normals / lengths[:, None]


def _near_normal(candidates, normal) -> int:
    for other, index in candidates:
        if (
            abs(other[0] - normal[0]) < NORMAL_MERGE
            and abs(other[1] - normal[1]) < NORMAL_MERGE
            and abs(other[2] - normal[2]) < NORMAL_MERGE
        ):
            return index
    return -1


def _vt_rows(mesh, kept_normals: Optional[np.ndarray], uv_layer, is_mirrored: bool) -> np.ndarray:
    """
    The mesh's VT rows (x y z nx ny nz s t in X-Plane's axes), one per triangle corner in X-Plane's winding. Values
    are Blender's single precision floats, as the exporter always wrote them
    """
    count = len(mesh.loop_triangles)
    tri_loops = np.empty(count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("loops", tri_loops)
    tri_vertices = np.empty(count * 3, dtype=np.int32)
    mesh.loop_triangles.foreach_get("vertices", tri_vertices)
    face_normals = np.empty(count * 3, dtype=np.float32)
    mesh.loop_triangles.foreach_get("normal", face_normals)
    polygons = np.empty(count, dtype=np.int32)
    mesh.loop_triangles.foreach_get("polygon_index", polygons)
    smooth_polygons = np.empty(len(mesh.polygons), dtype=bool)
    mesh.polygons.foreach_get("use_smooth", smooth_polygons)
    coords = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
    mesh.vertices.foreach_get("co", coords)

    # A reflection already changes Blender's CCW winding to CW, otherwise it is reversed for X-Plane as usual
    corner_order = [0, 1, 2] if is_mirrored else [2, 1, 0]
    loops = tri_loops.reshape(-1, 3)[:, corner_order].ravel()
    vertices = tri_vertices.reshape(-1, 3)[:, corner_order].ravel()
    smooth = np.repeat(smooth_polygons[polygons], 3)

    if kept_normals is not None:
        corner_normals = kept_normals.astype(np.float32)
    else:
        corner_normals = np.empty(len(mesh.loops) * 3, dtype=np.float32)
        if hasattr(mesh, "calc_normals_split"):  # Blender before 4.1
            mesh.loops.foreach_get("normal", corner_normals)
        else:
            mesh.corner_normals.foreach_get("vector", corner_normals)
        corner_normals = corner_normals.reshape(-1, 3)
    normals = np.where(
        smooth[:, None], corner_normals[loops], np.repeat(face_normals.reshape(-1, 3), 3, axis=0)
    )
    if is_mirrored:
        # Recalculated mesh normals follow the reflected faces inward
        flip = ~smooth if kept_normals is not None else np.ones(len(smooth), dtype=bool)
        normals = np.where(flip[:, None], -normals, normals)

    rows = np.zeros((len(loops), 8), dtype=np.float32)
    positions = coords.reshape(-1, 3)[vertices]
    rows[:, 0], rows[:, 1], rows[:, 2] = positions[:, 0], positions[:, 2], -positions[:, 1]
    rows[:, 3], rows[:, 4], rows[:, 5] = normals[:, 0], normals[:, 2], -normals[:, 1]
    if uv_layer:
        uvs = np.empty(len(mesh.loops) * 2, dtype=np.float32)
        uv_layer.data.foreach_get("uv", uvs)
        rows[:, 6:8] = uvs.reshape(-1, 2)[loops]
    return rows.astype(np.float64)


def _as_whole_rows(rows: np.ndarray) -> np.ndarray:
    """Each row as one value, so that numpy compares rows bit for bit"""
    whole = np.dtype((np.void, rows.dtype.itemsize * rows.shape[1]))
    return np.ascontiguousarray(rows).view(whole).ravel()


def _first_unique(rows: np.ndarray):
    """The distinct rows in the order they first come: (first index of each, each row's distinct number)"""
    _, first, inverse = np.unique(_as_whole_rows(rows), return_index=True, return_inverse=True)
    order = np.argsort(first)
    number = np.empty_like(order)
    number[order] = np.arange(len(order))
    return first[order], number[inverse.reshape(-1)]


def _groups(rows: np.ndarray):
    """Each row's group of equal rows, and how many rows each group has"""
    _, inverse, sizes = np.unique(_as_whole_rows(rows), return_inverse=True, return_counts=True)
    return inverse.reshape(-1), sizes


class XPlaneMesh:
    """
    Stores the data for the OBJ's mesh - its VT and IDX tables.

    Despite the name, there is only one XPlaneMesh per XPlaneFile,
    unlike the many XPlaneObjects per file
    """

    def __init__(self):
        # Contains all OBJ VT directives, data in the order as specified by the OBJ8 spec
        self.vertices = (
            []
        )  # type: List[Tuple[float, float, float, float, float, float, float, float]]
        # array - contains all face indices
        self.indices = array.array("i")  # type: List[int]
        # int - Stores the current global vertex index.
        self.globalindex = 0
        self.debug = []

    # Method: collectXPlaneObjects
    # Fills the <vertices> and <indices> from a list of <XPlaneObjects>.
    # This method works recursively on the children of each <XPlaneObject>.
    #
    # Parameters:
    #   list xplaneObjects - list of <XPlaneObjects>.
    def collectXPlaneObjects(self, xplaneObjects: List[XPlaneObject]) -> None:
        debug = getDebug()

        def getSortKey(xplaneObject):
            return xplaneObject.name

        # sort objects by name for consitent vertex and indices table output
        xplaneObjects = sorted(xplaneObjects, key=getSortKey)

        dg = bpy.context.evaluated_depsgraph_get()
        optimize = bpy.context.scene.xplane.optimize
        # Shared by the whole file: parts with the same shape in their own frames (a clock's digits) share vertices.
        # The rows of every mesh are collected and shared at the end
        pending: List[np.ndarray] = []
        corners = len(self.indices)
        for xplaneObject in xplaneObjects:
            if (
                xplaneObject.type == "MESH"
                and xplaneObject.xplaneBone
                and not xplaneObject.export_animation_only
            ):
                xplaneObject.indices[0] = corners

                # This is the heart of the exporter turning object into VT/IDX table:
                # - Get the mesh of the object with its modifiers
                # and transformations applied, rotated and moved by the bake matrix
                #
                # After that, the mesh needs to have some of it's data refreshed
                # - Recalc normals split
                # - Recalc tessface (now called loop triangles)

                # create a copy of the xplaneObject mesh with modifiers applied and triangulated
                evaluated_obj = xplaneObject.blenderObject.evaluated_get(dg)
                mesh = evaluated_obj.to_mesh(
                    preserve_all_data_layers=False, depsgraph=dg
                )

                xplaneObject.bakeMatrix = (
                    xplaneObject.xplaneBone.getBakeMatrixForAttached()
                )
                is_mirrored = xplaneObject.bakeMatrix.determinant() < 0
                # Custom normals are encoded relative to their faces and worked out again after a transform: a
                # reflection changes that basis, and a normal that points against its face (flipped or back
                # faces, common in imported aircraft) can come back pointing anywhere. Keep their directions
                kept_normals = (
                    _turned_corner_normals(mesh, xplaneObject.bakeMatrix)
                    if mesh.has_custom_normals
                    else None
                )
                mesh.transform(xplaneObject.bakeMatrix)

                if hasattr(mesh, "calc_normals_split"):
                    mesh.calc_normals_split()
                mesh.calc_loop_triangles()
                try:
                    uv_layer = mesh.uv_layers[xplaneObject.material.uv_name]
                except (KeyError, TypeError) as e:
                    uv_layer = None

                rows = _vt_rows(mesh, kept_normals, uv_layer, is_mirrored)
                if optimize:
                    pending.append(rows)
                else:
                    self.indices.extend(range(self.globalindex, self.globalindex + len(rows)))
                    self.vertices.extend(map(tuple, rows.tolist()))
                    self.globalindex += len(rows)
                corners += len(rows)
                if len(rows):
                    xplaneObject.indices[1] = corners

                evaluated_obj.to_mesh_clear()
        if pending:
            self._add_shared(np.concatenate(pending))

    def _add_shared(self, rows: np.ndarray) -> None:
        """
        Adds the file's VT rows (one per corner, in IDX order). A row the same as an earlier one, or one that differs
        from an earlier one at the same position and UV by Blender's rounding of normals only, reuses its vertex.
        Rows are compared as Python compares them (-0.0 is 0.0) and written as they first came
        """
        key = rows + 0.0
        first, corner_row = _first_unique(key)
        rows, key = rows[first], key[first]
        # Normals that differ by rounding only can only be at the same position and UV, usually a few rows
        place, counts = _groups(key[:, [0, 1, 2, 6, 7]])
        target = np.arange(len(rows))
        shared_place = np.nonzero(counts[place] > 1)[0]
        made = collections.defaultdict(list)
        for i, at, normal in zip(
            shared_place.tolist(), place[shared_place].tolist(), key[shared_place, 3:6].tolist()
        ):
            j = _near_normal(made[at], normal)
            if j == -1:
                made[at].append((normal, i))
            else:
                target[i] = j
        created = target == np.arange(len(rows))
        vertex = np.cumsum(created) - 1 + self.globalindex
        self.vertices.extend(map(tuple, rows[created].tolist()))
        self.globalindex += int(created.sum())
        self.indices.extend(vertex[target][corner_row].tolist())

    def writeVertices(self) -> str:
        """
        Turns the collected vertices into the OBJ's VT table
        """
        ######################################################################
        # WARNING! This is a hot path! So don't change it without profiling! #
        ######################################################################
        # print("Begin XPlaneMesh.writeVertices")
        # start = time.perf_counter()
        debug = getDebug()
        tab = f"\t"
        if debug:
            s = "".join(
                f"VT\t"
                f"{tab.join(floatToStr(component) for component in line)}"
                f"\t# {i}"
                f"\n"
                for i, line in enumerate(self.vertices)
            )
            # print("end XPlaneMesh.writeVertices " + str(time.perf_counter()-start))
            return s
        else:
            # One format per line is floatToStr's first try for all eight numbers. The rare line where one of them
            # needs an exponent is written again by floatToStr
            line_format = "VT\t" + "\t".join([f"{{:.{PRECISION_OBJ_FLOAT}g}}"] * 8) + "\n"
            lines = [line_format.format(*line) for line in self.vertices]
            joined = "".join(lines)
            if "e" not in joined:
                return joined
            for i, text in enumerate(lines):
                if "e" in text:
                    numbers = text[3:-1].split("\t")
                    line = self.vertices[i]
                    lines[i] = (
                        "VT\t"
                        + tab.join(n if "e" not in n else floatToStr(line[c]) for c, n in enumerate(numbers))
                        + "\n"
                    )
            return "".join(lines)

    def writeIndices(self) -> str:
        """
        Turns the collected indices into the OBJ's IDX10/IDX table
        """
        ######################################################################
        # WARNING! This is a hot path! So don't change it without profiling! #
        ######################################################################
        o = ""
        # print("Begin XPlaneMesh.writeIndices")
        # start = time.perf_counter()

        s_idx10 = "IDX10\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n"
        s_idx = "IDX\t%d\n"
        partition_point = len(self.indices) - (len(self.indices) % 10)

        if len(self.indices) >= 10:
            o += "".join(
                [
                    s_idx10 % (*self.indices[i : i + 10],)
                    for i in range(0, partition_point - 1, 10)
                ]
            )

        o += "".join(
            [
                s_idx % (self.indices[i])
                for i in range(partition_point, len(self.indices))
            ]
        )
        # print("End XPlaneMesh.writeIndices: " + str(time.perf_counter()-start))
        return o

    def write(self):
        o = ""
        debug = False

        verticesOut = self.writeVertices()
        o += verticesOut
        if len(verticesOut):
            o += "\n"
        o += self.writeIndices()

        return o
