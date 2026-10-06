"""Finds an OBJ's texture files and builds Blender materials that look like X-Plane renders them"""

import os
from typing import Dict, List, Optional, Tuple

import bpy

from io_xplane2blender import xplane_constants

from .common import ImportOptions, ImportReport
from .obj_parser import ObjFile

_EXTENSIONS = (".dds", ".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff")


def _unsupported_dds(path: str) -> bool:
    """True for DDS files in a format Blender cannot decode. Only DXT1, DXT3 and DXT5 and plain RGBA are safe"""
    if not path.lower().endswith(".dds"):
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(148)
    except OSError:
        return False
    # "DX10" in the pixel format's FourCC means the real format is in an extra header, BC7 and friends
    return header[:4] == b"DDS " and header[84:88] == b"DX10"


class TextureResolver:
    """Resolves an OBJ's texture paths on disk. A livery's replacement textures are checked first"""

    def __init__(
        self, obj_dir: str, livery_objects_dir: str = "", objects_root: str = ""
    ) -> None:
        self.obj_dir = obj_dir
        # liveries/<name>/objects replaces files of the aircraft's objects folder with the same relative path
        self.livery_objects_dir = livery_objects_dir
        self.objects_root = objects_root
        self._listing: Dict[str, Dict[str, str]] = {}

    def _find_in_dir(self, directory: str, name: str) -> Optional[str]:
        """Case insensitive lookup of `name`, which may have subfolders, inside directory"""
        current = directory
        parts = [
            p
            for p in name.replace("\\", "/").replace(":", "/").split("/")
            if p and p != "."
        ]
        for part in parts:
            if part == "..":
                current = os.path.dirname(current)
                continue
            if current not in self._listing:
                try:
                    self._listing[current] = {e.lower(): e for e in os.listdir(current)}
                except OSError:
                    return None
            entry = self._listing[current].get(part.lower())
            if entry is None:
                return None
            current = os.path.join(current, entry)
        return current if os.path.isfile(current) else None

    def resolve(self, texture_path: str) -> Optional[str]:
        if not texture_path or texture_path.lower() == "none":
            return None
        stem, extension = os.path.splitext(texture_path)
        candidates = [texture_path]
        if extension.lower() in _EXTENSIONS or not extension:
            candidates += [stem + e for e in _EXTENSIONS if e != extension.lower()]
        for candidate in candidates:
            if os.path.isabs(candidate) and os.path.isfile(candidate):
                return candidate
            base = self._find_in_dir(self.obj_dir, candidate)
            if base:
                return self._livery_override(base) or base
        return None

    def _livery_override(self, base: str) -> Optional[str]:
        if not (self.livery_objects_dir and self.objects_root):
            return None
        try:
            relative = os.path.relpath(base, self.objects_root)
        except ValueError:
            return None
        if relative.startswith(".."):
            return None
        stem, extension = os.path.splitext(relative)
        for candidate in [relative] + [
            stem + e for e in _EXTENSIONS if e != extension.lower()
        ]:
            found = self._find_in_dir(self.livery_objects_dir, candidate)
            if found:
                return found
        return None


class MaterialFactory:
    """Creates and caches the Blender materials for one OBJ"""

    def __init__(
        self,
        obj: ObjFile,
        resolver: TextureResolver,
        options: ImportOptions,
        report: ImportReport,
    ) -> None:
        self.obj = obj
        self.resolver = resolver
        self.options = options
        self.report = report
        self._cache: Dict[tuple, bpy.types.Material] = {}
        self._images: Dict[str, Optional[bpy.types.Image]] = {}
        self.base_name = os.path.splitext(os.path.basename(obj.path))[0] or "Material"
        self.diffuse_path = resolver.resolve(obj.texture)
        self.lit_path = resolver.resolve(obj.texture_lit)
        self.normal_path = resolver.resolve(
            obj.texture_normal or obj.texture_maps.get("normal", "")
        )
        self.material_gloss_path = resolver.resolve(
            obj.texture_maps.get("material_gloss", "")
        )
        self.gloss_path = resolver.resolve(obj.texture_maps.get("gloss", ""))
        for label, wanted, found in (
            ("TEXTURE", obj.texture, self.diffuse_path),
            ("TEXTURE_LIT", obj.texture_lit, self.lit_path),
            ("TEXTURE_NORMAL", obj.texture_normal, self.normal_path),
        ):
            if wanted and not found:
                report.warn(
                    f"{self.base_name}: {label} '{wanted}' was not found, the material has no texture"
                )

    # ---- images --------------------------------------------------------------------------
    def image(self, path: Optional[str], colorspace: str) -> Optional[bpy.types.Image]:
        if not path:
            return None
        key = f"{path}|{colorspace}"
        if key in self._images:
            return self._images[key]
        image = None
        try:
            if _unsupported_dds(path):
                self.report.warn(
                    f"{os.path.basename(path)} uses a DDS format Blender cannot read (BC6/BC7), it has no texture"
                )
            else:
                image = bpy.data.images.load(path, check_existing=True)
                image.colorspace_settings.name = colorspace
                # Keep unmultiplied color, X-Plane does not premultiply
                image.alpha_mode = "CHANNEL_PACKED"
        except RuntimeError as e:
            self.report.warn(f"Could not load texture {os.path.basename(path)}: {e}")
        self._images[key] = image
        return image

    # ---- materials -----------------------------------------------------------------------
    def material_for(self, state: dict, draped: bool = False) -> bpy.types.Material:
        """The Blender material for the material-level part of an attribute state"""
        key = self._key(state)
        if key in self._cache:
            return self._cache[key]
        name = self._name(state)
        mat = bpy.data.materials.new(name)
        self._cache[key] = mat
        self._set_xplane_props(mat, state)
        if self.options.import_materials:
            self._build_nodes(mat, state)
        return mat

    @staticmethod
    def _key(state: dict) -> tuple:
        return tuple(sorted((k, v) for k, v in state.items()))

    def _name(self, state: dict) -> str:
        suffix = []
        blend = state.get("blend")
        if blend:
            suffix.append(
                {
                    "blend": "blend",
                    "no_blend": "cutout",
                    "shadow_blend": "shadowblend",
                }.get(blend[0], blend[0])
            )
        if state.get("draw") == ("disable",):
            suffix.append("hidden")
        if "cockpit" in state:
            suffix.append("panel")
        if "light_level" in state:
            suffix.append("lit")
        return " ".join([self.base_name] + suffix)

    # ---- XPlane2Blender material settings ------------------------------------------------
    def _set_xplane_props(self, mat: bpy.types.Material, state: dict) -> None:
        x = mat.xplane
        x.draw = state.get("draw") != ("disable",)
        blend = state.get("blend")
        if blend is None:
            x.blend_v1000 = xplane_constants.BLEND_ON
        else:
            kind, *rest = blend
            ratio = float(rest[0]) if rest else 0.5
            x.blend_v1000 = {
                "blend": xplane_constants.BLEND_ON,
                "no_blend": xplane_constants.BLEND_OFF,
                "shadow_blend": xplane_constants.BLEND_SHADOW,
            }[kind]
            x.blendRatio = ratio
        shiny = state.get("shiny")
        if shiny:
            mat.specular_intensity = max(0.0, min(1.0, float(shiny[0])))
        elif self._global_specular() > 0:
            # GLOBAL_specular is what ATTR_shiny_rat defaults to for every mesh
            mat.specular_intensity = max(0.0, min(1.0, self._global_specular()))
        poly_os = state.get("poly_os")
        if poly_os:
            x.poly_os = int(float(poly_os[0]))
        x.solid_camera = "solid_camera" in state
        x.shadow_local = state.get("shadow") != ("off",)
        hard = state.get("hard")
        if hard:
            surface = (
                hard[0] if hard[0] != "deck" else (hard[1] if len(hard) > 1 else "")
            )
            valid = {
                i.identifier for i in x.bl_rna.properties["surfaceType"].enum_items
            }
            if surface in valid:
                x.surfaceType = surface
                x.deck = hard[0] == "deck"
        cockpit = state.get("cockpit")
        lit_only = state.get("cockpit_lit_only")
        if cockpit or lit_only is not None:
            x.cockpit_feature = xplane_constants.COCKPIT_FEATURE_PANEL
            luminance = None
            if cockpit and cockpit[0] == "region" and len(cockpit) > 1:
                region = str(int(float(cockpit[1])) + 1)
                if region in {
                    i.identifier
                    for i in x.bl_rna.properties["cockpit_region"].enum_items
                }:
                    x.cockpit_region = region
                luminance = cockpit[2] if len(cockpit) > 2 else None
            elif lit_only:
                luminance = lit_only[0]
            elif cockpit and cockpit[0] == "panel" and len(cockpit) > 1:
                luminance = cockpit[1]
            if luminance is not None:
                try:
                    x.cockpit_feature_use_luminance = True
                    x.cockpit_feature_luminance = max(
                        1, min(60000, int(float(luminance)))
                    )
                except ValueError:
                    pass
            if cockpit and cockpit[0] == "device" and len(cockpit) > 1:
                self._set_device(x, cockpit[1:])
        # Sticky attributes the add-on has no setting for are kept as custom attributes
        for key in (
            "depth",
            "layer_group",
            "diffuse",
            "diffuse_rgb",
            "emission_rgb",
            "specular_rgb",
            "landing_gear",
            "hud_glass",
            "cull",
            "shade",
            "rain",
            "wiper",
        ):
            if key in state:
                self._custom_attribute(mat, key, state[key])

    @staticmethod
    def _set_device(x, args) -> None:
        """ATTR_cockpit_device <name> <bus mask> <lighting channel> <auto adjust> [luminance]"""
        x.cockpit_feature = xplane_constants.COCKPIT_FEATURE_DEVICE
        name = args[0]
        known = {i.identifier for i in x.bl_rna.properties["device_name"].enum_items}
        if name in known:
            x.device_name = name
        else:
            x.device_name = xplane_constants.DEVICE_PLUGIN
            x.plugin_device = name
        try:
            bus = int(float(args[1])) if len(args) > 1 else 0
            for i in range(6):
                setattr(x, f"device_bus_{i}", bool(bus & (1 << i)))
            if len(args) > 2:
                x.device_lighting_channel = int(float(args[2]))
            if len(args) > 3:
                x.device_auto_adjust = bool(int(float(args[3])))
            if len(args) > 4:
                x.cockpit_feature_use_luminance = True
                x.cockpit_feature_luminance = max(1, min(60000, int(float(args[4]))))
        except ValueError:
            pass

    @staticmethod
    def _custom_attribute(mat: bpy.types.Material, key: str, value: tuple) -> None:
        names = {
            "depth": "ATTR_no_depth",
            "layer_group": "ATTR_layer_group",
            "diffuse": "ATTR_diffuse",
            "diffuse_rgb": "ATTR_diffuse_rgb",
            "emission_rgb": "ATTR_emission_rgb",
            "specular_rgb": "ATTR_specular_rgb",
            "landing_gear": "ATTR_landing_gear",
            "hud_glass": "ATTR_hud_glass",
            "cull": "ATTR_no_cull",
            "shade": "ATTR_shade_smooth",
            "rain": "ATTR_rain_scale",
            "wiper": "ATTR_wiper",
        }
        attribute = mat.xplane.customAttributes.add()
        attribute.name = names[key]
        attribute.value = " ".join(value)

    # ---- shader nodes --------------------------------------------------------------------
    def _build_nodes(self, mat: bpy.types.Material, state: dict) -> None:
        mat.use_nodes = True
        tree = mat.node_tree
        tree.nodes.clear()
        out = tree.nodes.new("ShaderNodeOutputMaterial")
        out.location = (900, 0)
        bsdf = tree.nodes.new("ShaderNodeBsdfPrincipled")
        bsdf.location = (600, 0)
        tree.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

        x = 0
        links = tree.links
        blend = state.get("blend")
        cutout = blend is not None and blend[0] in ("no_blend", "shadow_blend")
        ratio = float(blend[1]) if blend and len(blend) > 1 else 0.5
        # Without a texture the surface is a neutral grey, like X-Plane draws an untextured object
        bsdf.inputs["Base Color"].default_value = (0.8, 0.8, 0.8, 1.0)

        diffuse = self.image(self.diffuse_path, "sRGB")
        if diffuse:
            tex = self._image_node(tree, diffuse, (-300, 300))
            links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
            if cutout:
                gt = tree.nodes.new("ShaderNodeMath")
                gt.operation = "GREATER_THAN"
                gt.location = (200, 150)
                gt.inputs[1].default_value = ratio
                links.new(tex.outputs["Alpha"], gt.inputs[0])
                links.new(gt.outputs["Value"], bsdf.inputs["Alpha"])
            elif blend is not None and blend[0] == "blend" or blend is None:
                links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        self._set_blend_mode(mat, cutout, ratio, diffuse is not None)

        # Specular / gloss / metalness / normals
        shiny = state.get("shiny")
        specular_level = float(shiny[0]) if shiny else self._global_specular()
        spec_input = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs.get(
            "Specular"
        )
        normal_image = self.image(self.normal_path, "Non-Color")
        metalness_mode = self.obj.has_normal_metalness
        pbr_maps = bool(self.obj.texture_maps)
        rough = None
        if normal_image:
            tex = self._image_node(tree, normal_image, (-600, -150))
            # X-Plane only reads the red and green channels as the normal and rebuilds the rest, the blue channel
            # of many normal maps holds something else. It is the reflectance when NORMAL_METALNESS is used
            normal_color = self._reconstruct_normal(tree, tex)
            nm = tree.nodes.new("ShaderNodeNormalMap")
            nm.location = (200, -300)
            links.new(normal_color, nm.inputs["Color"])
            links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
            if not pbr_maps:
                # The alpha channel of the normal map is the specular strength
                mult = tree.nodes.new("ShaderNodeMath")
                mult.operation = "MULTIPLY"
                mult.location = (0, -450)
                mult.inputs[1].default_value = specular_level
                links.new(tex.outputs["Alpha"], mult.inputs[0])
                inv = tree.nodes.new("ShaderNodeMath")
                inv.operation = "SUBTRACT"
                inv.inputs[0].default_value = 1.0
                inv.location = (200, -450)
                links.new(mult.outputs["Value"], inv.inputs[1])
                links.new(inv.outputs["Value"], bsdf.inputs["Roughness"])
                rough = True
                if metalness_mode:
                    self._link_reflectance(tree, tex, bsdf, spec_input)
                elif spec_input is not None:
                    links.new(mult.outputs["Value"], spec_input)
        if pbr_maps:
            mg = self.image(self.material_gloss_path, "Non-Color")
            gloss = self.image(self.gloss_path, "Non-Color")
            if mg:
                tex = self._image_node(tree, mg, (-600, -500))
                sep = (
                    tree.nodes.new("ShaderNodeSeparateColor")
                    if hasattr(bpy.types, "ShaderNodeSeparateColor")
                    else tree.nodes.new("ShaderNodeSeparateRGB")
                )
                sep.location = (-300, -550)
                links.new(tex.outputs["Color"], sep.inputs[0])
                links.new(
                    sep.outputs.get("Red") or sep.outputs["R"], bsdf.inputs["Metallic"]
                )
                inv = tree.nodes.new("ShaderNodeMath")
                inv.operation = "SUBTRACT"
                inv.inputs[0].default_value = 1.0
                inv.location = (200, -600)
                links.new(sep.outputs.get("Green") or sep.outputs["G"], inv.inputs[1])
                links.new(inv.outputs["Value"], bsdf.inputs["Roughness"])
                rough = True
            elif gloss:
                tex = self._image_node(tree, gloss, (-600, -500))
                sep = (
                    tree.nodes.new("ShaderNodeSeparateColor")
                    if hasattr(bpy.types, "ShaderNodeSeparateColor")
                    else tree.nodes.new("ShaderNodeSeparateRGB")
                )
                sep.location = (-300, -550)
                links.new(tex.outputs["Color"], sep.inputs[0])
                inv = tree.nodes.new("ShaderNodeMath")
                inv.operation = "SUBTRACT"
                inv.inputs[0].default_value = 1.0
                inv.location = (200, -600)
                links.new(sep.outputs.get("Red") or sep.outputs["R"], inv.inputs[1])
                links.new(inv.outputs["Value"], bsdf.inputs["Roughness"])
                rough = True
        if rough is None:
            bsdf.inputs["Roughness"].default_value = (
                max(0.0, 1.0 - specular_level * 0.8)
                if (shiny or self._global_specular() > 0)
                else 0.9
            )
            if spec_input is not None:
                spec_input.default_value = min(0.5, specular_level * 0.5)

        # The _LIT texture is the night lighting, its strength is an import option
        lit = self.image(self.lit_path, "sRGB")
        emission_color = bsdf.inputs.get("Emission Color") or bsdf.inputs.get(
            "Emission"
        )
        if lit and emission_color is not None:
            tex = self._image_node(tree, lit, (-300, -800))
            links.new(tex.outputs["Color"], emission_color)
            strength = bsdf.inputs.get("Emission Strength")
            if strength is not None:
                strength.default_value = self.options.lit_strength

        if state.get("draw") == ("disable",):
            # Objects that are not drawn (manipulator hit boxes) become transparent
            bsdf.inputs["Alpha"].default_value = 0.0
            for link in list(bsdf.inputs["Alpha"].links):
                tree.links.remove(link)

    def _link_reflectance(self, tree, tex, bsdf, spec_input) -> None:
        """
        NORMAL_METALNESS: the blue channel is the base reflectance (F0), as exported by LR's Substance Painter preset.
        Plastic and paint sit near 0.04 to 0.15 and metals are high, so it drives the specular level directly
        (Principled 0.5 is F0 0.04) and the metallic input once it is clearly above any dielectric.
        """
        sep = (
            tree.nodes.new("ShaderNodeSeparateColor")
            if hasattr(bpy.types, "ShaderNodeSeparateColor")
            else tree.nodes.new("ShaderNodeSeparateRGB")
        )
        sep.location = (-300, -450)
        tree.links.new(tex.outputs["Color"], sep.inputs[0])
        blue = sep.outputs.get("Blue") or sep.outputs["B"]
        if spec_input is not None:
            level = tree.nodes.new("ShaderNodeMath")
            level.operation = "MULTIPLY"
            level.use_clamp = True
            level.location = (0, -650)
            level.inputs[1].default_value = 12.5
            tree.links.new(blue, level.inputs[0])
            tree.links.new(level.outputs["Value"], spec_input)
        metal = tree.nodes.new("ShaderNodeMapRange")
        metal.location = (0, -800)
        metal.inputs["From Min"].default_value = 0.2
        metal.inputs["From Max"].default_value = 0.45
        tree.links.new(blue, metal.inputs["Value"])
        tree.links.new(metal.outputs["Result"], bsdf.inputs["Metallic"])

    def _global_specular(self) -> float:
        values = self.obj.globals.get("GLOBAL_specular")
        try:
            return float(values[-1][0]) if values else 0.0
        except (ValueError, IndexError):
            return 0.0

    def _image_node(self, tree, image, location) -> bpy.types.ShaderNode:
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        node.location = location
        node.interpolation = "Linear"
        node.extension = "REPEAT"
        return node

    def _reconstruct_normal(self, tree, tex):
        """Normal maps that store only X and Y in red and green: rebuild Z and return a color socket"""
        sep = (
            tree.nodes.new("ShaderNodeSeparateColor")
            if hasattr(bpy.types, "ShaderNodeSeparateColor")
            else tree.nodes.new("ShaderNodeSeparateRGB")
        )
        sep.location = (-400, -150)
        tree.links.new(tex.outputs["Color"], sep.inputs[0])
        red = sep.outputs.get("Red") or sep.outputs["R"]
        green = sep.outputs.get("Green") or sep.outputs["G"]

        def math(op, a=None, b=None, loc=(0, 0), value=None):
            node = tree.nodes.new("ShaderNodeMath")
            node.operation = op
            node.location = loc
            if value is not None:
                node.inputs[1].default_value = value
            return node

        # x = r * 2 - 1, y = g * 2 - 1
        xs = math("MULTIPLY_ADD", loc=(-250, -100))
        xs.inputs[1].default_value = 2.0
        xs.inputs[2].default_value = -1.0
        tree.links.new(red, xs.inputs[0])
        ys = math("MULTIPLY_ADD", loc=(-250, -200))
        ys.inputs[1].default_value = 2.0
        ys.inputs[2].default_value = -1.0
        tree.links.new(green, ys.inputs[0])
        # z = sqrt(max(0, 1 - x^2 - y^2))
        x2 = math("POWER", loc=(-100, -100), value=2.0)
        tree.links.new(xs.outputs["Value"], x2.inputs[0])
        y2 = math("POWER", loc=(-100, -200), value=2.0)
        tree.links.new(ys.outputs["Value"], y2.inputs[0])
        total = math("ADD", loc=(50, -150))
        tree.links.new(x2.outputs["Value"], total.inputs[0])
        tree.links.new(y2.outputs["Value"], total.inputs[1])
        rest = math("SUBTRACT", loc=(150, -150))
        rest.inputs[0].default_value = 1.0
        tree.links.new(total.outputs["Value"], rest.inputs[1])
        z = math("SQRT", loc=(250, -150))
        tree.links.new(rest.outputs["Value"], z.inputs[0])
        # back into 0..1 for the Normal Map node
        combine = tree.nodes.new("ShaderNodeCombineXYZ")
        combine.location = (350, -150)
        tree.links.new(xs.outputs["Value"], combine.inputs["X"])
        tree.links.new(ys.outputs["Value"], combine.inputs["Y"])
        tree.links.new(z.outputs["Value"], combine.inputs["Z"])
        scale = tree.nodes.new("ShaderNodeVectorMath")
        scale.operation = "MULTIPLY_ADD"
        scale.location = (500, -150)
        scale.inputs[1].default_value = (0.5, 0.5, 0.5)
        scale.inputs[2].default_value = (0.5, 0.5, 0.5)
        tree.links.new(combine.outputs["Vector"], scale.inputs[0])
        return scale.outputs["Vector"]

    @staticmethod
    def _set_blend_mode(
        mat: bpy.types.Material, cutout: bool, ratio: float, has_texture: bool
    ) -> None:
        """The viewport blend mode, which differs between Blender versions"""
        if hasattr(mat, "surface_render_method"):  # Blender 4.2 and later
            mat.surface_render_method = (
                "DITHERED" if (cutout or not has_texture) else "BLENDED"
            )
        elif hasattr(mat, "blend_method"):
            mat.blend_method = "CLIP" if cutout else "BLEND"
            if cutout and hasattr(mat, "alpha_threshold"):
                mat.alpha_threshold = ratio
            if hasattr(mat, "shadow_method"):
                mat.shadow_method = "HASHED"
