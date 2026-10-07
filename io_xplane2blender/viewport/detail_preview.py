"""
Detail texture preview: shows a file's detail textures (decals) on its materials in Material Preview and renders,
approximately as X-Plane draws them. A color detail is tiled at its scale and multiplied in at twice its brightness
(mid grey changes nothing) as strongly as its keys say; a normal detail is tiled and added to the surface's normal.
Keys read the base color texture's channels.

The preview is shader nodes named "XP2B Detail ...", in a frame, between the Principled BSDF and what fed it.
Removing it puts the links back as they were. The exporter never reads shader nodes, and From Materials looks
through the preview to the base textures.
"""

import os
from typing import List, Optional, Tuple

import bpy

from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.xplane_helpers import is_path_decal_lib, material_nodes

PREFIX = I.PREVIEW_PREFIX
FROM_NODE, FROM_SOCKET = I.PREVIEW_FROM_NODE, I.PREVIEW_FROM_SOCKET
KEYS = ("red_key", "green_key", "blue_key", "alpha_key", "modulator", "constant")
original_source = I.preview_original


def is_preview(node) -> bool:
    return node.name.startswith(PREFIX)


def _bsdf(material: bpy.types.Material):
    tree = material_nodes(material)
    if tree is None:
        return None
    return next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None)


def _socket(sockets, name: str, kind: Optional[str] = None):
    return next(s for s in sockets if s.name == name and s.enabled and (kind is None or s.type == kind))


class _Builder:
    def __init__(self, material: bpy.types.Material, bsdf):
        self.tree = material.node_tree
        self.bsdf = bsdf
        self.frame = self.new("NodeFrame", "Preview")
        self.frame.label = "X-Plane Detail Texture Preview"
        self.x = bsdf.location.x - 900
        self.y = bsdf.location.y
        self._coords = None

    def new(self, kind: str, name: str):
        node = self.tree.nodes.new(kind)
        node.name = node.label = f"{PREFIX} {name}"
        if kind != "NodeFrame":
            node.parent = self.frame
            node.location = (self.x, self.y)
            self.y -= 160
        return node

    def link(self, from_socket, to_socket) -> None:
        self.tree.links.new(from_socket, to_socket)

    def value(self, number: float):
        node = self.new("ShaderNodeValue", "Value")
        node.outputs[0].default_value = number
        return node.outputs[0]

    def coords(self):
        if self._coords is None:
            self._coords = self.new("ShaderNodeTexCoord", "Coordinates")
        return self._coords

    def tiled_image(self, image, layer, prefix: str, colorspace: str):
        projected = getattr(layer, f"{prefix}_projected")
        mapping = self.new("ShaderNodeMapping", "Tiling")
        if projected:
            self.link(self.coords().outputs["Object"], mapping.inputs["Vector"])
            scale = (getattr(layer, f"{prefix}_x_scale"), getattr(layer, f"{prefix}_y_scale"), 1.0)
        else:
            self.link(self.coords().outputs["UV"], mapping.inputs["Vector"])
            scale = (getattr(layer, f"{prefix}_scale"),) * 2 + (1.0,)
        mapping.inputs["Scale"].default_value = scale
        texture = self.new("ShaderNodeTexImage", "Texture")
        texture.image = image
        texture.extension = "REPEAT"
        image.colorspace_settings.name = colorspace
        self.link(mapping.outputs["Vector"], texture.inputs["Vector"])
        return texture

    def strength(self, channels: List, keys: Tuple[float, ...]):
        """constant + the sum of each key times its channel, clamped to 0 to 1"""
        total = self.value(keys[-1])
        for channel, key in zip(channels, keys[:-1]):
            if key == 0 or channel is None:
                continue
            step = self.new("ShaderNodeMath", "Key")
            step.operation = "MULTIPLY_ADD"
            self.link(channel, step.inputs[0])
            step.inputs[1].default_value = key
            self.link(total, step.inputs[2])
            total = step.outputs[0]
        clamp = self.new("ShaderNodeMath", "Strength")
        clamp.operation, clamp.use_clamp = "ADD", True
        clamp.inputs[1].default_value = 0.0
        self.link(total, clamp.inputs[0])
        return clamp.outputs[0]

    def remember(self, last_node, original) -> None:
        last_node[FROM_NODE] = original.node.name if original is not None else ""
        last_node[FROM_SOCKET] = original.identifier if original is not None else ""


def _load(path: str, report: List[str]) -> Optional[bpy.types.Image]:
    full = bpy.path.abspath(path)
    if is_path_decal_lib(path):
        report.append(f"{os.path.basename(path)} is a decal library, its texture can't be previewed")
        return None
    if not os.path.isfile(full):
        report.append(f"{path} was not found")
        return None
    return bpy.data.images.load(full, check_existing=True)


def _channels(b: _Builder, base_socket, layer):
    split = b.new("ShaderNodeSeparateColor", "Base Channels")
    b.link(base_socket, split.inputs[0])
    if base_socket.node.type == "TEX_IMAGE":
        alpha = base_socket.node.outputs["Alpha"]
    else:
        alpha_input = b.bsdf.inputs.get("Alpha")
        alpha = alpha_input.links[0].from_socket if alpha_input is not None and alpha_input.is_linked else None
    modulator = None
    image = _load(layer.texture_modulator, []) if layer.texture_modulator else None
    if image is not None:
        texture = b.new("ShaderNodeTexImage", "Modulator")
        texture.image = image
        b.link(b.coords().outputs["UV"], texture.inputs["Vector"])
        modulator = texture.outputs["Color"]
    return [split.outputs[0], split.outputs[1], split.outputs[2], alpha, modulator]


def _base_color(b: _Builder):
    target = b.bsdf.inputs["Base Color"]
    if target.is_linked:
        return target.links[0].from_socket
    color = b.new("ShaderNodeRGB", "Base")
    color.outputs[0].default_value = target.default_value
    return color.outputs[0]


def add_preview(material: bpy.types.Material, layer, report: List[str]) -> bool:
    """Adds the preview of the file's detail textures to a material. Returns whether there was anything to show"""
    bsdf = _bsdf(material)
    if bsdf is None:
        return False
    color_images = [(i, _load(getattr(layer, f"file_decal{i}"), report)) for i in (1, 2) if getattr(layer, f"file_decal{i}")]
    normal_images = [
        (i, _load(getattr(layer, f"file_normal_decal{i}"), report))
        for i in (1, 2)
        if getattr(layer, f"file_normal_decal{i}")
    ]
    color_images = [(i, image) for i, image in color_images if image is not None]
    normal_images = [(i, image) for i, image in normal_images if image is not None]
    if not color_images and not normal_images:
        return False

    b = _Builder(material, bsdf)
    original_color = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].is_linked else None
    base = _base_color(b)
    channels = _channels(b, base, layer)

    color = base
    for i, image in color_images:
        texture = b.tiled_image(image, layer, f"decal{i}", "sRGB")
        doubled = b.new("ShaderNodeVectorMath", "Twice")
        doubled.operation = "SCALE"
        b.link(texture.outputs["Color"], doubled.inputs[0])
        _socket(doubled.inputs, "Scale").default_value = 2.0
        mix = b.new("ShaderNodeMix", f"Color {i}")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        b.link(b.strength(channels, tuple(getattr(layer, f"rgb_decal{i}_{k}") for k in KEYS)), mix.inputs[0])
        b.link(color, _socket(mix.inputs, "A", "RGBA"))
        b.link(doubled.outputs[0], _socket(mix.inputs, "B", "RGBA"))
        color = _socket(mix.outputs, "Result", "RGBA")
    if color_images:
        b.remember(color.node, original_color)
        b.link(color, bsdf.inputs["Base Color"])

    target = bsdf.inputs["Normal"]
    original_normal = target.links[0].from_socket if target.is_linked else None
    normal = original_normal
    for i, image in normal_images:
        texture = b.tiled_image(image, layer, f"normal_decal{i}", "Non-Color")
        normal_map = b.new("ShaderNodeNormalMap", f"Normal {i}")
        b.link(texture.outputs["Color"], normal_map.inputs["Color"])
        b.link(b.strength(channels, tuple(getattr(layer, f"normal_decal{i}_{k}") for k in KEYS)), normal_map.inputs["Strength"])
        if normal is None:
            normal = normal_map.outputs["Normal"]
            continue
        geometry = b.new("ShaderNodeNewGeometry", "Surface")
        added = b.new("ShaderNodeVectorMath", "Add Normals")
        added.operation = "ADD"
        b.link(normal, added.inputs[0])
        b.link(normal_map.outputs["Normal"], added.inputs[1])
        less = b.new("ShaderNodeVectorMath", "Less Surface")
        less.operation = "SUBTRACT"
        b.link(added.outputs[0], less.inputs[0])
        b.link(geometry.outputs["Normal"], less.inputs[1])
        unit = b.new("ShaderNodeVectorMath", "Normalized")
        unit.operation = "NORMALIZE"
        b.link(less.outputs[0], unit.inputs[0])
        normal = unit.outputs[0]
    if normal_images:
        b.remember(normal.node, original_normal)
        b.link(normal, target)
    return True


def remove_preview(material: bpy.types.Material) -> bool:
    """Takes the preview out of a material and puts its links back. Returns whether there was one"""
    bsdf = _bsdf(material)
    if bsdf is None:
        return False
    tree = material.node_tree
    nodes = [n for n in tree.nodes if is_preview(n)]
    if not nodes:
        return False
    for name in ("Base Color", "Normal"):
        target = bsdf.inputs[name]
        if target.is_linked and is_preview(target.links[0].from_node):
            source = original_source(target.links[0].from_node)
            tree.links.remove(target.links[0])
            if source is not None:
                tree.links.new(source, target)
    for node in nodes:
        tree.nodes.remove(node)
    return True


def file_materials(owner) -> List[bpy.types.Material]:
    found = []
    for obj in I.file_objects(owner):
        for slot in getattr(obj, "material_slots", ()):
            if slot.material is not None and slot.material not in found:
                found.append(slot.material)
    return found


class XPLANE_OT_detail_preview(bpy.types.Operator):
    """Show this file's detail textures on its materials in Material Preview, approximately as X-Plane draws them.
    Nothing exported changes"""

    bl_idname = "xplane.detail_preview"
    bl_label = "Preview Detail Textures"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    remove: bpy.props.BoolProperty(name="Remove", description="Take the preview out again", default=False)

    def execute(self, context):
        from io_xplane2blender.ui.state import active_file

        owner = active_file(context)
        if owner is None:
            return {"CANCELLED"}
        materials = file_materials(owner)
        problems: List[str] = []
        changed = 0
        for material in materials:
            removed = remove_preview(material)
            if self.remove:
                changed += removed
            else:
                changed += add_preview(material, owner.xplane.layer, problems)
        for problem in sorted(set(problems)):
            self.report({"WARNING"}, problem)
        if self.remove:
            self.report({"INFO"}, f"Detail texture preview removed from {changed} material(s)")
        elif changed:
            self.report({"INFO"}, f"Detail textures shown on {changed} material(s), in Material Preview shading")
        else:
            self.report({"WARNING"}, "No detail texture could be shown: set one, and give the materials a Principled BSDF")
        return {"FINISHED"}


classes = (XPLANE_OT_detail_preview,)
