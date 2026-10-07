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
    _, first, inverse = np.unique(keys, axis=0, return_index=True, return_inverse=True)
    inverse = inverse.reshape(-1)
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
    mesh.from_pydata(coords.tolist(), [], faces.tolist())
    mesh.polygons.foreach_set("material_index", material_slots.astype(np.int32))
    mesh.polygons.foreach_set("use_smooth", np.ones(len(faces), dtype=bool))

    uv_layer = mesh.uv_layers.new(name="UVMap")
    uv_layer.data.foreach_set("uv", uvs.astype(np.float32).ravel())

    if hasattr(
        mesh, "use_auto_smooth"
    ):  # Blender before 4.1 needs this for custom normals
        mesh.use_auto_smooth = True
    mesh.normals_split_custom_set(normals.tolist())
    mesh.update()
    return mesh, len(faces)
