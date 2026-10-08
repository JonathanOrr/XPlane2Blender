"""Finds an OBJ's texture files and builds Blender materials that look like X-Plane renders them"""

import os
from typing import Dict, Optional

import bpy

from io_xplane2blender import xplane_constants

from .common import ImportOptions, ImportReport
from .material_nodes import MaterialNodes
from .obj_parser import ObjFile
from .textures import TextureResolver, _unsupported_dds


class MaterialFactory(MaterialNodes):
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
        else:
            # GLOBAL_specular is what ATTR_shiny_rat defaults to for every mesh, and without it X-Plane's default is 0
            # (not Blender's 0.5, which the exporter would write)
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
            "cull": "ATTR_no_cull",
            "shade": "ATTR_shade_smooth",
            "rain": "ATTR_rain_scale",
            "wiper": "ATTR_wiper",
        }
        attribute = mat.xplane.customAttributes.add()
        attribute.name = names[key]
        attribute.value = " ".join(value)
