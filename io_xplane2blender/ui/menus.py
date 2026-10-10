"""
Menus: kinds of control and light, moving objects into files, and the X-Plane entries of the 3D View's
Add and right-click menus, with the things they add.
"""

import bpy

from io_xplane2blender import xplane_anim_presets
from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.xplane_props.light import LIGHT_TYPE_ITEMS

from .ops_file import XPLANE_OT_move_to_file, XPLANE_OT_new_file
from .ops_object import XPLANE_OT_set_control_kind, XPLANE_OT_set_light_kind

# The kinds of light with their names, as the Type setting lists them
LIGHT_KINDS = tuple((kind, label, help) for kind, label, help, _ in LIGHT_TYPE_ITEMS)

ATTACHMENTS = (
    (C.EMPTY_USAGE_WHEEL, "Wheel", "Where a landing gear wheel is drawn"),
    (C.EMPTY_USAGE_MAGNET, "Tablet Mount", "Where a VR tablet can be attached"),
    (C.EMPTY_USAGE_EMITTER_PARTICLE, "Particle Emitter", "Where particles (smoke, sparks) come from"),
)


def light_kind_label(light_type: str) -> str:
    return next((label for kind, label, _ in LIGHT_KINDS if kind == light_type), "Unknown")


class XPLANE_MT_control_kind(bpy.types.Menu):
    bl_idname = "XPLANE_MT_control_kind"
    bl_label = "Kind Of Control"

    def draw(self, context):
        row = self.layout.row()
        for group in I.GROUPS:
            col = row.column()
            col.label(text=group)
            for manip_type, kind in I.CONTROL_KINDS.items():
                if kind.group == group:
                    col.operator(XPLANE_OT_set_control_kind.bl_idname, text=kind.label).kind = manip_type


class XPLANE_MT_light_kind(bpy.types.Menu):
    bl_idname = "XPLANE_MT_light_kind"
    bl_label = "Kind Of Light"

    def draw(self, context):
        for kind, label, _ in LIGHT_KINDS:
            self.layout.operator(XPLANE_OT_set_light_kind.bl_idname, text=label).kind = kind


class XPLANE_MT_move_to_file(bpy.types.Menu):
    bl_idname = "XPLANE_MT_move_to_file"
    bl_label = "Move To File"

    def draw(self, context):
        files = [f for f in I.export_files(context.scene) if isinstance(f, bpy.types.Collection)]
        for owner in files:
            self.layout.operator(XPLANE_OT_move_to_file.bl_idname, text=I.file_name(owner)).collection = owner.name
        if files:
            self.layout.separator()
        self.layout.operator(XPLANE_OT_new_file.bl_idname, icon="ADD")


def _place_and_select(context, obj) -> None:
    obj.location = context.scene.cursor.location
    context.collection.objects.link(obj)
    for other in context.selected_objects:
        other.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


class XPLANE_OT_add_click_zone(bpy.types.Operator):
    """Add an invisible box that can be clicked in X-Plane, at the 3D cursor"""

    bl_idname = "xplane.add_click_zone"
    bl_label = "Click Zone"
    bl_options = {"REGISTER", "UNDO"}

    size: bpy.props.FloatProperty(name="Size", default=0.02, min=0.001, unit="LENGTH")

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=self.size, location=context.scene.cursor.location)
        obj = context.object
        obj.name = "click zone"
        material = bpy.data.materials.get("X-Plane Click Zone")
        if material is None:
            material = bpy.data.materials.new("X-Plane Click Zone")
            material.xplane.draw = False
            material.diffuse_color = (1.0, 0.3, 0.1, 0.35)
        obj.data.materials.append(material)
        obj.display_type = "WIRE"
        obj.show_in_front = True
        manip = obj.xplane.manip
        manip.enabled = True
        manip.type = C.MANIP_COMMAND
        manip.cursor = C.MANIP_CURSOR_BUTTON
        return {"FINISHED"}


class XPLANE_OT_add_light(bpy.types.Operator):
    """Add an X-Plane light at the 3D cursor"""

    bl_idname = "xplane.add_light"
    bl_label = "Light"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(items=[(k, label, h) for k, label, h in LIGHT_KINDS[:3]])

    @classmethod
    def description(cls, context, properties):
        return next((f"Add at the 3D cursor: {h[0].lower()}{h[1:]}" for k, _, h in LIGHT_KINDS if k == properties.kind), "")

    def execute(self, context):
        data = bpy.data.lights.new(light_kind_label(self.kind).lower(), "POINT" if self.kind == C.LIGHT_CUSTOM else "SPOT")
        data.xplane.type = self.kind
        if self.kind == C.LIGHT_CUSTOM:
            # The exporter writes the power of a glow sprite as its alpha: opaque
            data.energy = 1.0
        _place_and_select(context, bpy.data.objects.new(data.name, data))
        return {"FINISHED"}


class XPLANE_OT_add_attachment(bpy.types.Operator):
    """Add an empty that X-Plane uses as a wheel, tablet mount or particle emitter, at the 3D cursor"""

    bl_idname = "xplane.add_attachment"
    bl_label = "Attachment Point"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(items=ATTACHMENTS)

    @classmethod
    def description(cls, context, properties):
        return next((f"Add an empty at the 3D cursor: {h[0].lower()}{h[1:]}" for k, _, h in ATTACHMENTS if k == properties.kind), "")

    def execute(self, context):
        obj = bpy.data.objects.new(self.kind.replace("_", " "), None)
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = 0.1
        obj.xplane.special_empty_props.special_type = self.kind
        _place_and_select(context, obj)
        return {"FINISHED"}


class XPLANE_MT_add(bpy.types.Menu):
    bl_idname = "XPLANE_MT_add"
    bl_label = "X-Plane"

    def draw(self, context):
        layout = self.layout
        layout.operator(XPLANE_OT_add_click_zone.bl_idname, icon="RESTRICT_SELECT_OFF")
        layout.separator()
        for kind, label, _ in LIGHT_KINDS[:3]:
            layout.operator(XPLANE_OT_add_light.bl_idname, text=f"Light: {label}", icon="LIGHT").kind = kind
        layout.separator()
        for kind, label, _ in ATTACHMENTS:
            layout.operator(XPLANE_OT_add_attachment.bl_idname, text=label, icon="EMPTY_ARROWS").kind = kind


class XPLANE_MT_object_context(bpy.types.Menu):
    bl_idname = "XPLANE_MT_object_context"
    bl_label = "X-Plane"

    def draw(self, context):
        layout = self.layout
        layout.menu(XPLANE_MT_control_kind.bl_idname, text="Make Clickable As", icon="RESTRICT_SELECT_OFF")
        layout.separator()
        layout.operator(xplane_anim_presets.XPLANE_OT_anim_push_button.bl_idname, text="Animate As Push Button")
        layout.operator(xplane_anim_presets.XPLANE_OT_anim_switch.bl_idname, text="Animate As Switch")
        layout.operator(xplane_anim_presets.XPLANE_OT_anim_range.bl_idname, text="Animate As Knob / Lever")
        layout.separator()
        layout.menu(XPLANE_MT_move_to_file.bl_idname, icon="FILE")


def add_menu_entry(self, context):
    self.layout.menu(XPLANE_MT_add.bl_idname, icon="AUTO")


def context_menu_entry(self, context):
    self.layout.separator()
    self.layout.menu(XPLANE_MT_object_context.bl_idname, icon="AUTO")


classes = (
    XPLANE_MT_control_kind,
    XPLANE_MT_light_kind,
    XPLANE_MT_move_to_file,
    XPLANE_OT_add_click_zone,
    XPLANE_OT_add_light,
    XPLANE_OT_add_attachment,
    XPLANE_MT_add,
    XPLANE_MT_object_context,
)
