"""Turns slices of an OBJ's vertex and index tables into a Blender mesh"""

from typing import List, Optional, Tuple

import bpy
import numpy as np


def build_mesh(
    name: str,
    vertices: np.ndarray,
    indices: np.ndarray,
    runs: List[Tuple[int, int, int]],
    scale: float = 1.0,
) -> Tuple[Optional[bpy.types.Mesh], int]:
    """
    vertices is the OBJ's (N, 8) table: x y z nx ny nz s t. indices is the whole IDX table.
    runs are (offset, count, material_slot) for each TRIS.
    Returns (mesh or None if nothing was left, triangle count).
    """
    triangle_blocks = []
    slots = []
    for offset, count, slot in runs:
        block = indices[offset : offset + (count // 3) * 3].reshape(-1, 3)
        triangle_blocks.append(block)
        slots.append(np.full(len(block), slot, dtype=np.int32))
    if not triangle_blocks:
        return None, 0
    triangles = np.concatenate(triangle_blocks)
    material_slots = np.concatenate(slots)

    # Indices that point outside the vertex table can't be drawn, X-Plane would not either
    valid = ((triangles >= 0) & (triangles < len(vertices))).all(axis=1)
    if not valid.all():
        triangles, material_slots = triangles[valid], material_slots[valid]
    if len(triangles) == 0:
        return None, 0

    # Drop triangles that reference the same vertex twice
    keep = (
        (triangles[:, 0] != triangles[:, 1])
        & (triangles[:, 1] != triangles[:, 2])
        & (triangles[:, 0] != triangles[:, 2])
    )
    triangles, material_slots = triangles[keep], material_slots[keep]
    if len(triangles) == 0:
        return None, 0

    # X-Plane (x, y up, z back) to Blender (x, y forward, z up)
    positions = np.empty((len(vertices), 3), dtype=np.float64)
    positions[:, 0] = vertices[:, 0]
    positions[:, 1] = -vertices[:, 2]
    positions[:, 2] = vertices[:, 1]
    positions *= scale

    # Weld vertices that only differ by their normal or UV so that the mesh is connected
    used = np.unique(triangles)
    keys = np.round(positions[used] / max(scale, 1e-9), 5)
    first, inverse = _unique_rows(keys)
    remap = np.full(len(vertices), -1, dtype=np.int64)
    remap[used] = inverse
    coords = positions[used][first]

    # X-Plane triangles are clockwise, Blender's are counter-clockwise
    reversed_triangles = triangles[:, ::-1]
    faces = remap[reversed_triangles]
    welded_ok = (
        (faces[:, 0] != faces[:, 1])
        & (faces[:, 1] != faces[:, 2])
        & (faces[:, 0] != faces[:, 2])
    )
    # Triangles with no area (corners on a line, less than a micrometre wide) draw nothing, and Blender's normals
    # around them change when the mesh is turned (an imported part rotated and applied): they are left out
    a, b, c = (coords[faces[:, i]] for i in range(3))
    edges = np.stack(
        [
            np.linalg.norm(b - a, axis=1),
            np.linalg.norm(c - b, axis=1),
            np.linalg.norm(a - c, axis=1),
        ]
    )
    width = np.linalg.norm(np.cross(b - a, c - a), axis=1) / np.maximum(
        edges.max(axis=0, initial=0.0), 1e-12
    )
    welded_ok &= width >= 1e-6 * scale
    if not welded_ok.all():
        faces = faces[welded_ok]
        reversed_triangles = reversed_triangles[welded_ok]
        material_slots = material_slots[welded_ok]
    if len(faces) == 0:
        return None, 0

    loop_vertices = reversed_triangles.reshape(-1)
    normals = np.empty((len(loop_vertices), 3), dtype=np.float64)
    normals[:, 0] = vertices[loop_vertices, 3]
    normals[:, 1] = -vertices[loop_vertices, 5]
    normals[:, 2] = vertices[loop_vertices, 4]
    lengths = np.linalg.norm(normals, axis=1)
    bad = lengths < 1e-8
    lengths[bad] = 1.0
    normals /= lengths[:, None]
    normals[bad] = (0.0, 0.0, 1.0)
    uvs = vertices[loop_vertices, 6:8]

    mesh = bpy.data.meshes.new(name)
    _fill(mesh, coords, faces)
    mesh.polygons.foreach_set("material_index", material_slots.astype(np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))

    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_layer.data.foreach_set("uv", uvs.astype(np.float32).ravel())

    if hasattr(
        mesh, "use_auto_smooth"
    ):  # Blender before 4.1 needs this for custom normals
        mesh.use_auto_smooth = True
    mesh.normals_split_custom_set(normals.tolist())
    _keep_folded_normals(mesh, normals)
    mesh.update()
    return mesh, len(faces)


def _unique_rows(keys: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    np.unique(keys, axis=0, return_index=True, return_inverse=True) without the unique rows, in a third of the
    time: the rows sorted by x, then y, then z, each first of its equals
    """
    order = np.lexsort(keys.T[::-1])
    in_order = keys[order]
    starts = np.ones(len(keys), dtype=bool)
    starts[1:] = (in_order[1:] != in_order[:-1]).any(axis=1)
    inverse = np.empty(len(keys), dtype=np.int64)
    inverse[order] = np.cumsum(starts) - 1
    return order[starts], inverse


def _fill(mesh, coords: np.ndarray, faces: np.ndarray) -> None:
    """What Mesh.from_pydata does for triangles, from arrays and without marking the faces flat first"""
    mesh.vertices.add(len(coords))
    mesh.loops.add(faces.size)
    mesh.polygons.add(len(faces))
    mesh.vertices.foreach_set("co", coords.astype(np.float32).ravel())
    mesh.polygons.foreach_set("loop_start", np.arange(0, faces.size, 3, dtype=np.int32))
    mesh.polygons.foreach_set("vertices", faces.astype(np.int32).ravel())
    mesh.update(calc_edges=True)


def _keep_folded_normals(mesh, normals: np.ndarray) -> None:
    """
    Blender keeps a custom normal relative to the faces that join around a vertex. Where they fold back on each
    other their directions cancel and Blender keeps nothing (a 737 copilot's collar): the edges of such vertices
    are made sharp, so each face is on its own, and the normals are set again
    """
    lost = np.abs(corner_normals(mesh) - normals).max(axis=1) > 1e-2
    if not lost.any():
        return
    corner_vertices = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get("vertex_index", corner_vertices)
    vertices = np.zeros(len(mesh.vertices), dtype=bool)
    vertices[corner_vertices[lost]] = True
    edge_vertices = np.empty(len(mesh.edges) * 2, dtype=np.int64)
    mesh.edges.foreach_get("vertices", edge_vertices)
    sharp = vertices[edge_vertices.reshape(-1, 2)].any(axis=1)
    if hasattr(mesh, "calc_normals_split"):  # Blender before 4.1
        old = np.zeros(len(mesh.edges), dtype=bool)
        mesh.edges.foreach_get("use_edge_sharp", old)
        mesh.edges.foreach_set("use_edge_sharp", old | sharp)
    else:
        attribute = mesh.attributes.get("sharp_edge") or mesh.attributes.new(
            "sharp_edge", "BOOLEAN", "EDGE"
        )
        old = np.zeros(len(mesh.edges), dtype=bool)
        attribute.data.foreach_get("value", old)
        attribute.data.foreach_set("value", old | sharp)
    mesh.normals_split_custom_set(normals.tolist())


def corner_normals(mesh) -> np.ndarray:
    """The normal of every corner (loop) of the mesh, as an (N, 3) array"""
    out = np.empty(len(mesh.loops) * 3, dtype=np.float64)
    if hasattr(
        mesh, "calc_normals_split"
    ):  # Blender before 4.1 (its corner_normals is empty)
        mesh.calc_normals_split()
        mesh.loops.foreach_get("normal", out)
    else:
        mesh.corner_normals.foreach_get("vector", out)
    return out.reshape(-1, 3)


def transform_mesh(mesh, matrix) -> None:
    """
    Moves the mesh's vertices and turns its corner normals with them. Blender keeps a custom normal relative to its
    faces and works it out again after a transform, and a normal that points against its face (Laminar's flipped
    and back faces) can come back pointing anywhere: the normals are set again, turned
    """
    normals = corner_normals(mesh)
    mesh.transform(matrix)
    turn = np.array(matrix.to_3x3().inverted_safe().transposed())
    normals = normals @ turn.T
    lengths = np.linalg.norm(normals, axis=1)
    lengths[lengths < 1e-12] = 1.0
    normals /= lengths[:, None]
    mesh.normals_split_custom_set(normals.tolist())
    _keep_folded_normals(mesh, normals)
