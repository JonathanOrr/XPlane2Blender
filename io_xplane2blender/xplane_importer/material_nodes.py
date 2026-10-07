"""Builds a material's shader nodes so that it looks the way X-Plane draws it"""

import bpy

# Above this base reflectance X-Plane treats the material as metal
DIELECTRIC_F0_MAX = 0.08


class MaterialNodes:
    """The shader node half of MaterialFactory"""

    def _build_nodes(self, mat: bpy.types.Material, state: dict) -> None:
        if bpy.app.version < (5, 0, 0):
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
                    self._link_reflectance(tree, tex, "B", bsdf, spec_input)
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
                self._link_reflectance(tree, tex, "R", bsdf, spec_input)
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

    def _link_reflectance(self, tree, tex, channel, bsdf, spec_input) -> None:
        """
        The F0 (base reflectance) channel: blue of a NORMAL_METALNESS normal map, red of an XP12 material map.
        X-Plane treats 0 to 0.08 as dielectric (0.04 is plastic or paint, 0.06 glass) and above 0.08 as metalness,
        with the dielectric reflection held at 0.08. Principled 0.5 is F0 0.04, so the specular level is F0 / 0.08.
        """
        sep = (
            tree.nodes.new("ShaderNodeSeparateColor")
            if hasattr(bpy.types, "ShaderNodeSeparateColor")
            else tree.nodes.new("ShaderNodeSeparateRGB")
        )
        sep.location = (-300, -450)
        tree.links.new(tex.outputs["Color"], sep.inputs[0])
        names = {"R": "Red", "B": "Blue"}
        f0 = sep.outputs.get(names[channel]) or sep.outputs[channel]
        if spec_input is not None:
            capped = tree.nodes.new("ShaderNodeMath")
            capped.operation = "MINIMUM"
            capped.location = (-100, -650)
            capped.inputs[1].default_value = DIELECTRIC_F0_MAX
            tree.links.new(f0, capped.inputs[0])
            level = tree.nodes.new("ShaderNodeMath")
            level.operation = "DIVIDE"
            level.location = (100, -650)
            level.inputs[1].default_value = DIELECTRIC_F0_MAX
            tree.links.new(capped.outputs["Value"], level.inputs[0])
            tree.links.new(level.outputs["Value"], spec_input)
        metal = tree.nodes.new("ShaderNodeMapRange")
        metal.location = (0, -800)
        metal.inputs["From Min"].default_value = DIELECTRIC_F0_MAX
        metal.inputs["From Max"].default_value = 1.0
        tree.links.new(f0, metal.inputs["Value"])
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
        # EEVEE sorts a blended material per object, never per triangle. With these two on (Blender's default) the
        # triangles of one mesh show through each other and the holes move as the camera orbits. Off, the surface
        # writes depth, which is what X-Plane's z-buffer does. Cycles ignores both
        if hasattr(mat, "show_transparent_back"):
            mat.show_transparent_back = False
        if hasattr(mat, "use_transparency_overlap"):
            mat.use_transparency_overlap = False
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
