import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING

import bpy

from ..xplane_constants import (
    EMPTY_USAGE_EMITTER_PARTICLE,
    EMPTY_USAGE_EMITTER_SOUND,
    NORMAL_MAPS_TEXTURES,
)
from ..xplane_helpers import effective_normal_metalness, logger
from . import xplane_header_decals, xplane_header_rain
from .xplane_attribute import XPlaneAttribute
from .xplane_attributes import XPlaneAttributes

if TYPE_CHECKING:
    from .xplane_file import XPlaneFile

# The order directives are written in
ATTRIBUTES = (
    "PARTICLE_SYSTEM",
    "COCKPIT_REGION",
    "GLOBAL_cockpit_lit",
    "slung_load_weight",
    "TEXTURE",
    "TEXTURE_LIT",
    "TEXTURE_NORMAL",
    "TEXTURE_MAP normal",
    "TEXTURE_MAP material_gloss",
    "TEXTURE_MAP gloss",
    "NORMAL_METALNESS",
    *xplane_header_decals.NAMES,
    *xplane_header_rain.NAMES,
    "GLOBAL_specular",
    "GLOBAL_luminance",
    "BLEND_GLASS",
    "POINT_COUNTS",
)

TEXTURES = (("TEXTURE", "texture"), ("TEXTURE_LIT", "texture_lit"))


class XPlaneHeader:
    """
    Writes the OBJ8 header of an X-Plane 12 aircraft or cockpit object: textures, file-wide
    settings and POINT_COUNTS.
    """

    def __init__(self, xplaneFile: "XPlaneFile") -> None:
        self.xplaneFile = xplaneFile
        self.attributes = XPlaneAttributes()
        for name in ATTRIBUTES:
            self.attributes.add(XPlaneAttribute(name, None))

    def _export_dir(self) -> str:
        filename = self.xplaneFile.filename
        if os.path.isabs(filename):
            return os.path.dirname(os.path.normpath(filename))
        blenddir = os.path.dirname(bpy.context.blend_data.filepath)
        return os.path.dirname(os.path.abspath(os.path.normpath(os.path.join(blenddir, filename))))

    def _init(self):
        """
        Collects the header. It must run after everything else is collected, since some of it
        (like GLOBAL_specular) depends on the materials in the file.
        """
        options = self.xplaneFile.options
        filename = self.xplaneFile.filename
        export_dir = self._export_dir()

        def relative(path: str) -> str:
            return self.get_path_relative_to_dir(path, export_dir)

        if options.slungLoadWeight > 0:
            self.attributes["slung_load_weight"].setValue(options.slungLoadWeight)

        # Only the normal and shine textures of the file's choice: the others may still hold paths from before
        for name, prop in TEXTURES + NORMAL_MAPS_TEXTURES[options.normal_maps]:
            path = getattr(options, prop)
            if path:
                try:
                    self.attributes[name].setValue(relative(path))
                except (OSError, ValueError):
                    pass

        xplane_header_decals.collect(self.attributes, options, relative)

        texture_normal = (
            self.attributes["TEXTURE_NORMAL"].getValue() or self.attributes["TEXTURE_MAP normal"].getValue()
        )
        normal_metalness = effective_normal_metalness(self.xplaneFile)
        if texture_normal:
            self.attributes["NORMAL_METALNESS"].setValue(normal_metalness)
        elif normal_metalness:
            logger.warn(f"{filename}: No Normal Texture found, ignoring use of Normal Metalness")

        xplane_header_rain.collect(self.attributes, options.rain, filename, relative)

        self.attributes["BLEND_GLASS"].setValue(options.blend_glass)

        for i in range(int(options.cockpit_regions)):
            region = options.cockpit_region[i]
            if i == 0:
                self.attributes["COCKPIT_REGION"].removeValues()
            self.attributes["COCKPIT_REGION"].addValue(
                (
                    region.left,
                    region.top,  # bad name alert! Should have been "bottom"
                    region.left + (2**region.width),
                    region.top + (2**region.height),
                )
            )

        self._collect_particle_system(relative)

        self.attributes["POINT_COUNTS"].setValue(
            (self.xplaneFile.mesh.globalindex, 0, 0, len(self.xplaneFile.mesh.indices))
        )

        if options.specular_override:
            # The file's own default shininess (an imported file's GLOBAL_specular, or none: 0)
            if options.specular > 0:
                self.attributes["GLOBAL_specular"].setValue(options.specular)
            self.xplaneFile.commands.written["ATTR_shiny_rat"] = options.specular
        elif self.xplaneFile.reference_material and normal_metalness:
            self.attributes["GLOBAL_specular"].setValue(1.0)
            # Every ATTR_shiny_rat would repeat it, so they are treated as already written
            self.xplaneFile.commands.written["ATTR_shiny_rat"] = 1.0

        if options.luminance_override:
            self.attributes["GLOBAL_luminance"].setValue(options.luminance)

        self.attributes["GLOBAL_cockpit_lit"].setValue(True)

        for attr in options.customAttributes:
            self.attributes.add(XPlaneAttribute(attr.name, attr.value))

    def _collect_particle_system(self, relative) -> None:
        pss_file = self.xplaneFile.options.particle_system_file
        try:
            pss = relative(pss_file)
        except (OSError, ValueError):
            return

        emitters = {EMPTY_USAGE_EMITTER_PARTICLE, EMPTY_USAGE_EMITTER_SOUND}
        if not any(
            obj.type == "EMPTY" and obj.blenderObject.xplane.special_empty_props.special_type in emitters
            for obj in self.xplaneFile.get_xplane_objects()
        ):
            logger.warn(f"Particle System File {pss} is given, but no emitter objects are used")
        if not pss.endswith(".pss"):
            logger.error(f"Particle System File {pss} must be a .pss file")
        self.attributes["PARTICLE_SYSTEM"].setValue(pss)

    def get_path_relative_to_dir(self, res_path: str, export_dir: str) -> str:
        """
        Returns the resource path relative to the exported OBJ

        res_path   - The relative or absolute resource path (such as .png, .dds, .pss or .dcl)
                  as found in an RNA field
        export_dir - Absolute path to directory of OBJ export

        Raises ValueError or OSError for invalid paths or use of `//` not at the start of the respath
        """
        res_path = res_path.strip()
        if res_path.startswith("./") or res_path.startswith(".\\"):
            res_path = res_path.replace("./", "//").replace(".\\", "//").strip()

        # 9. '//', or none means "none", empty is not written -> str.replace
        if res_path == "":
            raise ValueError
        elif res_path == "//" or res_path == "none":
            return "none"
        # 2. '//' is the .blend folder or CWD if not saved, -> bpy.path.abspath if bpy.data.filename else cwd
        elif res_path.startswith("//") and bpy.data.filepath:
            res_path = Path(bpy.path.abspath(res_path))
        elif res_path.startswith("//") and not bpy.data.filepath:
            res_path = Path(".") / Path(res_path[2:])
        # 7. Invalid paths are a validation error
        elif "//" in res_path and not res_path.startswith("//"):
            logger.error(f"'//' is used not at the start of the path '{res_path}'")
            raise ValueError
        elif not Path(res_path).suffix:
            logger.error(f"Resource path '{res_path}' must be a supported file type, has no extension")
            raise ValueError
        elif Path(res_path).suffix.lower() not in {".png", ".dds", ".pss", ".dcl"}:
            logger.error(f"Resource path '{res_path}' must be a supported file type, is {Path(res_path).suffix}")
            raise ValueError
        else:
            res_path = Path(res_path)

        old_cwd = os.getcwd()
        if bpy.data.filepath:
            # This makes '.' the .blend file directory
            os.chdir(Path(bpy.data.filepath).parent)
        else:
            os.chdir(Path(export_dir))

        try:
            # 1. '.' is CWD -> os.path.abspath
            # 3. All paths are given '/' separators -> str.replace
            # 4. '..'s are resolved, '.' is a no-op -> os.path.abspath
            # 5. All paths must be relative to the OBJ -> Path.relative_to(does order of args matter)?
            # 7. Invalid paths are a validation error
            # 8. Paths are minimal, "./path/tex.png" is "path/tex.png" -> os.path.abspath
            # 10. Absolute paths are okay as long as we can make a relative path os.path.relpath
            # Normalize without following symlinks: the OBJ must reference the user's path.
            rel_path = os.path.relpath(os.path.abspath(res_path), export_dir).replace("\\", "/")
        except OSError:
            logger.error(f"Path '{res_path}' is invalid")
            os.chdir(old_cwd)
            raise
        except ValueError:
            logger.error(f"Cannot make relative path across disk drives for path '{res_path}'")
            # 6. If not possible (different drive letter), validation error Path.relative_to ValueError
            # 7. Invalid paths are a validation error
            os.chdir(old_cwd)
            raise
        else:
            os.chdir(old_cwd)
            if any(c.isspace() for c in rel_path):
                logger.error(
                    f"Texture path '{rel_path}' contains a space, which breaks the OBJ "
                    "file format (tokens are whitespace-separated). Rename the file or "
                    "folder, or use underscores instead of spaces."
                )
                raise ValueError
            return rel_path

    def write(self) -> str:
        """
        Writes the collected Blender and XPlane2Blender data
        as content for the OBJ
        """
        self._init()

        # line ending types (I = UNIX/DOS, A = MacOS)
        o = "A\n" if "Mac OS" in platform.system() else "I\n"
        o += "800\nOBJ\n\n"

        self.attributes.move_to_end("POINT_COUNTS")

        for attr in self.attributes.values():
            values = attr.value
            if values[0] is None:
                continue
            if len(values) > 1:
                for vi in range(len(values)):
                    o += "%s\t%s\n" % (attr.name, attr.getValueAsString(vi))
            elif isinstance(values[0], bool):
                # True is written as the bare word, False is left out
                if values[0]:
                    o += "%s\n" % attr.name
            else:
                o += "%s\t%s\n" % (attr.name, attr.getValueAsString())

        return o
