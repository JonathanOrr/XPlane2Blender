"""
Operators for the active object or bone: making it clickable, animating it, copying its settings.
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_helpers
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender import xplane_light_tools
from io_xplane2blender.xplane_ops import getDatarefValuePath, removeDatarefFCurve

from .state import selected_or_active

TARGETS = (("object", "Object", ""), ("bone", "Bone", ""))


def animated(context, target: str):
    """(settings with datarefs, the ID the keys are on, the bone or None) for the active object or bone"""
    if target == "bone":
        obj = context.object
        if obj is None or obj.type != "ARMATURE":
            return None, None, None
        # The Bone tab has context.bone, elsewhere the armature's active bone is meant
        bone = getattr(context, "bone", None) or obj.data.bones.active
        return (bone, obj.data, bone) if bone is not None else (None, None, None)
    obj = context.object
    return obj, obj, None


class XPLANE_OT_set_control_kind(bpy.types.Operator):
    """Make the selected objects clickable, as this kind of control"""

    bl_idname = "xplane.set_control_kind"
    bl_label = "Set Kind Of Control"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    kind: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        kind = I.CONTROL_KINDS.get(properties.kind)
        return kind.help if kind else ""

    def execute(self, context):
        new = I.CONTROL_KINDS[self.kind]
        meshes = [o for o in selected_or_active(context) if o.type == "MESH"]
        for obj in meshes:
            manip = obj.xplane.manip
            old_cursor = I.control_kind(manip).cursor
            fresh = not manip.enabled
            manip.enabled = True
            manip.type = self.kind
            if fresh or manip.cursor == old_cursor:
                manip.cursor = new.cursor
        if not meshes:
            self.report({"WARNING"}, "Select the meshes to make clickable")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{len(meshes)} object(s) are now: {new.label}")
        return {"FINISHED"}


class XPLANE_OT_copy_to_selected(bpy.types.Operator):
    """Copy these X-Plane settings from the active object to the other selected objects"""

    bl_idname = "xplane.copy_to_selected"
    bl_label = "Copy To Selected"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    what: bpy.props.EnumProperty(
        items=(
            ("CLICK", "Clickable", ""),
            ("GLOW", "Glow", ""),
            ("VISIBILITY", "Shows / Hides", ""),
            ("LIGHT", "Light", ""),
            ("ATTACHMENT", "Attachment", ""),
        )
    )

    @classmethod
    def poll(cls, context):
        return context.object is not None and len(context.selected_objects) > 1

    def execute(self, context):
        source = context.object
        done = sum(
            1 for target in context.selected_objects if target != source and I.copy_settings(self.what, source, target)
        )
        self.report({"INFO"}, f"Copied to {done} object(s)")
        return {"FINISHED"}


class XPLANE_OT_add_dataref(bpy.types.Operator):
    """Add a dataref to the active object or bone"""

    bl_idname = "xplane.add_dataref"
    bl_label = "Add Dataref"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    anim_type: bpy.props.EnumProperty(
        items=(
            (C.ANIM_TYPE_TRANSFORM, "Moves", "Keyframe the movement against the dataref"),
            (C.ANIM_TYPE_SHOW, "Show When", "Show it while the dataref is in a range"),
            (C.ANIM_TYPE_HIDE, "Hide When", "Hide it while the dataref is in a range"),
        )
    )
    target: bpy.props.EnumProperty(items=TARGETS, default="object")

    def execute(self, context):
        owner, _, _ = animated(context, self.target)
        if owner is None:
            return {"CANCELLED"}
        dataref = owner.xplane.datarefs.add()
        dataref.anim_type = self.anim_type
        if self.anim_type != C.ANIM_TYPE_TRANSFORM:
            dataref.show_hide_v1, dataref.show_hide_v2 = 1.0, 1.0
        return {"FINISHED"}


class XPLANE_OT_remove_dataref(bpy.types.Operator):
    """Remove this dataref and its keyframes"""

    bl_idname = "xplane.remove_dataref"
    bl_label = "Remove Dataref"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: bpy.props.IntProperty()
    target: bpy.props.EnumProperty(items=TARGETS, default="object")

    def execute(self, context):
        owner, id_data, bone = animated(context, self.target)
        if owner is None or not 0 <= self.index < len(owner.xplane.datarefs):
            return {"CANCELLED"}
        owner.xplane.datarefs.remove(self.index)
        # The keys of the datarefs after this one move down with them
        removeDatarefFCurve(id_data, self.index, bone)
        return {"FINISHED"}


def _make_linear(id_data, frame: float, paths) -> None:
    for fcurve in xplane_helpers.get_action_fcurves(id_data):
        if any(fcurve.data_path.startswith(p) for p in paths):
            for key in fcurve.keyframe_points:
                if key.co[0] == frame:
                    key.interpolation = "LINEAR"


def _rotation_path(owner) -> str:
    return {"QUATERNION": "rotation_quaternion", "AXIS_ANGLE": "rotation_axis_angle"}.get(
        owner.rotation_mode, "rotation_euler"
    )


class XPLANE_OT_key_pose(bpy.types.Operator):
    """Key where it is now at this dataref value: pose it, type the value, click. Keys are linear, like X-Plane"""

    bl_idname = "xplane.key_pose"
    bl_label = "Key This Pose"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: bpy.props.IntProperty()
    target: bpy.props.EnumProperty(items=TARGETS, default="object")

    def execute(self, context):
        owner, id_data, bone = animated(context, self.target)
        if owner is None:
            return {"CANCELLED"}
        frame = context.scene.frame_current
        value_path = getDatarefValuePath(self.index, bone)
        if bone is None:
            moving, prefix, group = owner, "", "Object Transforms"
        else:
            moving, prefix, group = context.object.pose.bones[bone.name], f'pose.bones["{bone.name}"].', bone.name
        rotation = _rotation_path(moving)
        id_data.keyframe_insert(data_path=value_path, frame=frame, group="XPlane Datarefs")
        moving.keyframe_insert(data_path="location", frame=frame, group=group)
        moving.keyframe_insert(data_path=rotation, frame=frame, group=group)
        _make_linear(id_data, frame, [value_path])
        _make_linear(context.object, frame, [prefix + "location", prefix + rotation])
        return {"FINISHED"}


class XPLANE_OT_go_to_frame(bpy.types.Operator):
    """Go to this key to see or change the pose"""

    bl_idname = "xplane.go_to_frame"
    bl_label = "Go To Key"
    bl_options = {"INTERNAL"}

    frame: bpy.props.FloatProperty()

    def execute(self, context):
        context.scene.frame_set(int(round(self.frame)))
        return {"FINISHED"}


class XPLANE_OT_select_object(bpy.types.Operator):
    """Select this object"""

    bl_idname = "xplane.select_object"
    bl_label = "Select"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    name: bpy.props.StringProperty()

    def execute(self, context):
        obj = bpy.data.objects.get(self.name)
        if obj is None or obj.name not in context.view_layer.objects or context.mode != "OBJECT":
            return {"CANCELLED"}
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {"FINISHED"}


class XPLANE_OT_set_light_kind(bpy.types.Operator):
    """Set what kind of X-Plane light the selected lights are"""

    bl_idname = "xplane.set_light_kind"
    bl_label = "Set Light Kind"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    kind: bpy.props.StringProperty()

    def execute(self, context):
        lights = [o for o in selected_or_active(context) if o.type == "LIGHT"]
        for obj in lights:
            obj.data.xplane.type = self.kind
            xplane_light_tools.seed_params(obj.data.xplane, obj)
            if self.kind in (C.LIGHT_SPILL_CUSTOM, C.LIGHT_AUTOMATIC) and obj.data.type not in ("POINT", "SPOT"):
                obj.data.type = "SPOT"
        return {"FINISHED"} if lights else {"CANCELLED"}


classes = (
    XPLANE_OT_set_control_kind,
    XPLANE_OT_copy_to_selected,
    XPLANE_OT_add_dataref,
    XPLANE_OT_remove_dataref,
    XPLANE_OT_key_pose,
    XPLANE_OT_go_to_frame,
    XPLANE_OT_select_object,
    XPLANE_OT_set_light_kind,
)
