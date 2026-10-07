"""Helpers for the importer tests: tiny files written to a temporary folder"""

import os
import struct
import tempfile
import zlib
from typing import Dict, Optional


def write_png(
    path: str, width: int = 4, height: int = 4, rgba=(200, 100, 50, 255)
) -> str:
    """Writes a solid color RGBA png without needing any image library"""
    raw = b"".join(b"\x00" + bytes(rgba) * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return (
            struct.pack(">I", len(data))
            + body
            + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
        )

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return path


def write_file(path: str, text: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        f.write(text)
    return path


class TempFolder:
    """A temporary folder that is removed when the test is done"""

    def __init__(self) -> None:
        self._dir = tempfile.TemporaryDirectory(prefix="xp2b_import_")
        self.path = self._dir.name

    def join(self, *parts: str) -> str:
        return os.path.join(self.path, *parts)

    def cleanup(self) -> None:
        self._dir.cleanup()


# A triangle on the ground that faces up in X-Plane: clockwise seen from above
TRIANGLE_VT = (
    "VT\t0\t0\t0\t0\t1\t0\t0\t0\n"
    "VT\t0\t0\t-1\t0\t1\t0\t0\t1\n"
    "VT\t1\t0\t0\t0\t1\t0\t1\t0\n"
)


def obj_text(
    body: str,
    header: str = "",
    version: int = 800,
    vertices: str = TRIANGLE_VT,
    indices: str = "IDX10\t0 1 2\n",
    tris: Optional[str] = "TRIS\t0 3\n",
) -> str:
    """A complete OBJ file made of the pieces a test cares about"""
    return (
        f"A\n{version}\nOBJ\n{header}"
        f"{vertices}{indices}POINT_COUNTS\t3\t0\t0\t3\n"
        f"{body}{tris or ''}"
    )
