"""
Animation presets for cockpit controls: a push button that moves while its command is held, a switch with a number
of positions, and a knob or lever over a range. Each one keys a dataref and the object's movement in one step, on
as many selected objects as needed, where by hand it means keyframing a dataref value and a transform per position
per object.

Movement is along or around the object's own axis, from where it stands at frame 1. Keys are linear, as X-Plane
interpolates them. Objects that are already animated are left alone unless Replace is ticked.
"""

import math
from typing import List, Optional, Sequence, Tuple

import bpy
from mathutils import Quaternion, Vector

from .xplane_helpers import get_action_channelbag, get_action_fcurves

AXES = (
    ("X", "X", "The object's own X axis"),
    ("Y", "Y", "The object's own Y axis"),
    ("Z", "Z", "The object's own Z axis"),
    ("-X", "-X", "Against the object's own X axis"),
    ("-Y", "-Y", "Against the object's own Y axis"),
    ("-Z", "-Z", "Against the object's own Z axis"),
)
MOTIONS = (
    ("ROTATE", "Rotate", "Turn around the axis (degrees)"),
    ("MOVE", "Move", "Slide along the axis (millimeters)"),
)
FRAME_STEP = 10
# A rotation turned into Euler angles through a quaternion loses whole turns, so big turns are keyed in steps
MAX_ROTATION_STEP = math.radians(90.0)
# Where the presets found the object before animating it, so Replace starts from there again
REST_PROPERTY = "xplane_preset_rest"
ANIMATED_PATHS = ("location", "rotation_euler", "rotation_quaternion", "rotation_axis_angle")


def axis_vector(axis: str) -> Vector:
    sign = -1.0 if axis.startswith("-") else 1.0
    return Vector({"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[axis[-1]]) * sign


def _remove_animation(obj: bpy.types.Object) -> None:
    """Removes the X-Plane datarefs and the movement keys, other animation of the object stays"""
    obj.xplane.datarefs.clear()
    fcurves = get_action_fcurves(obj)
    if not fcurves:
        return
    channelbag = get_action_channelbag(obj)
    owner = channelbag.fcurves if channelbag is not None else obj.animation_data.action.fcurves
    for fc in list(fcurves):
        if fc.data_path in ANIMATED_PATHS or fc.data_path.startswith("xplane.datarefs"):
            owner.remove(fc)


def _make_linear(obj: bpy.types.Object) -> None:
    for fc in get_action_fcurves(obj):
        if fc.data_path in ANIMATED_PATHS or fc.data_path.startswith("xplane.datarefs"):
            for key in fc.keyframe_points:
                key.interpolation = "LINEAR"


def _rotation_samples(values: Sequence[float], offsets: Sequence[float]) -> List[Tuple[float, float]]:
    """The keys with extra ones in between where the turn between two keys is over 90 degrees. X-Plane interpolates
    linearly between keys, so the extra keys do not change the motion"""
    samples = [(values[0], offsets[0])]
    for (v0, o0), (v1, o1) in zip(zip(values, offsets), zip(values[1:], offsets[1:])):
        steps = max(1, math.ceil(abs(o1 - o0) / MAX_ROTATION_STEP - 1e-9))
        for k in range(1, steps + 1):
            t = k / steps
            samples.append((v0 + (v1 - v0) * t, o0 + (o1 - o0) * t))
    return samples


def animate(
    obj: bpy.types.Object,
    dataref: str,
    values: Sequence[float],
    offsets: Sequence[float],
    motion: str,
    axis: str,
    loop: float = 0.0,
    replace: bool = False,
) -> Optional[str]:
    """
    Keys the dataref at each value and the object turned (radians) or moved (meters) by the matching offset from its
    pose at frame 1. Returns None when done, or why the object was left alone
    """
    if not dataref.strip():
        return "no dataref or command"
    if obj.xplane.datarefs and not replace:
        return "already animated"
    scene = bpy.context.scene
    frame_before = scene.frame_current
    scene.frame_set(1)
    if replace:
        _remove_animation(obj)
    if obj.rotation_mode in ("QUATERNION", "AXIS_ANGLE"):
        obj.rotation_mode = "XYZ"  # Blender keeps the orientation when the mode changes
    stored = obj.get(REST_PROPERTY)
    if replace and stored is not None and len(stored) == 6:
        # Frame 1 shows the first position of the old animation, not where the object stood
        obj.location = stored[:3]
        obj.rotation_euler = stored[3:]
    rest_location = obj.location.copy()
    rest_rotation = obj.rotation_euler.copy()
    obj[REST_PROPERTY] = [*rest_location, *rest_rotation]
    rest_quaternion = rest_rotation.to_quaternion()
    direction = axis_vector(axis)

    dataref_item = obj.xplane.datarefs.add()
    dataref_item.path = dataref.strip()
    dataref_item.anim_type = "transform"
    dataref_item.loop = loop
    index = len(obj.xplane.datarefs) - 1
    previous = rest_rotation.copy()
    keys = list(zip(values, offsets)) if motion == "MOVE" else _rotation_samples(values, offsets)
    for i, (value, offset) in enumerate(keys):
        frame = 1 + i * FRAME_STEP
        obj.xplane.datarefs[index].value = value
        obj.keyframe_insert(data_path=f"xplane.datarefs[{index}].value", frame=frame, group="XPlane Datarefs")
        if motion == "MOVE":
            obj.location = rest_location + rest_quaternion @ (direction * offset)
            obj.keyframe_insert(data_path="location", frame=frame, group="Location")
        else:
            turned = rest_quaternion @ Quaternion(direction, offset)
            obj.rotation_euler = turned.to_euler(obj.rotation_mode, previous)
            previous = obj.rotation_euler.copy()
            obj.keyframe_insert(data_path="rotation_euler", frame=frame, group="Rotation")
    _make_linear(obj)
    scene.frame_set(frame_before)
    return None


def fill_name(text: str, obj: bpy.types.Object) -> str:
    """{name} in a dataref or command becomes the object's name"""
    return text.replace("{name}", obj.name)


class _Preset:
    """Shared by the presets: the objects they work on and the report afterwards"""

    replace: bpy.props.BoolProperty(
        name="Replace",
        description="Replace the X-Plane animation of objects that already have one, otherwise they are left alone",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def finish(self, done: int, skipped: List[Tuple[str, str]]):
        text = f"Animated {done} object(s)"
        reasons = {}
        for name, reason in skipped:
            reasons.setdefault(reason, []).append(name)
        for reason, names in reasons.items():
            shown = ", ".join(names[:3]) + ("..." if len(names) > 3 else "")
            text += f"; {len(names)} left alone, {reason} ({shown})"
        if reasons.get("already animated"):
            text += ". Tick Replace to redo them"
        self.report({"WARNING"} if skipped and not done else {"INFO"}, text)
        return {"FINISHED"} if done else {"CANCELLED"}


class XPLANE_OT_anim_push_button(_Preset, bpy.types.Operator):
    """Animate the selected objects as push buttons that move in while their command is held (CMND= dataref)"""

    bl_idname = "xplane.anim_push_button"
    bl_label = "Push Button"
    bl_options = {"REGISTER", "UNDO"}

    command: bpy.props.StringProperty(
        name="Command",
        description="The command that pushes the button. Empty uses each object's manipulator command. {name} becomes the object's name",
    )
    axis: bpy.props.EnumProperty(name="Pushes Along", items=AXES, default="-Z")
    distance: bpy.props.FloatProperty(name="Travel (mm)", default=2.0, min=0.0, soft_max=50.0)
    make_clickable: bpy.props.BoolProperty(
        name="Make Clickable",
        description="Give objects without a manipulator a command manipulator for the same command",
        default=True,
    )

    def execute(self, context):
        done, skipped = 0, []
        for obj in context.selected_objects:
            manip = obj.xplane.manip
            command = fill_name(self.command, obj).strip()
            if not command and manip.enabled:
                command = manip.command or manip.positive_command
            reason = animate(
                obj,
                f"CMND={command}" if command else "",
                (0.0, 1.0),
                (0.0, self.distance / 1000.0),
                "MOVE",
                self.axis,
                replace=self.replace,
            )
            if reason == "no dataref or command":
                reason = "no command"
            if reason:
                skipped.append((obj.name, reason))
                continue
            if self.make_clickable and not manip.enabled:
                manip.enabled = True
                manip.type = "command"
                manip.cursor = "button"
                manip.command = command
            done += 1
        return self.finish(done, skipped)


class XPLANE_OT_anim_switch(_Preset, bpy.types.Operator):
    """Animate the selected objects as switches with a number of positions, each a dataref value"""

    bl_idname = "xplane.anim_switch"
    bl_label = "Switch"
    bl_options = {"REGISTER", "UNDO"}

    dataref: bpy.props.StringProperty(
        name="Dataref",
        description="The dataref that holds the switch position. Empty uses each object's manipulator dataref. {name} becomes the object's name",
    )
    positions: bpy.props.IntProperty(name="Positions", default=2, min=2, max=12)
    first_value: bpy.props.FloatProperty(name="First Value", default=0.0)
    value_step: bpy.props.FloatProperty(name="Value Step", default=1.0)
    motion: bpy.props.EnumProperty(name="Motion", items=MOTIONS, default="ROTATE")
    axis: bpy.props.EnumProperty(name="Axis", items=AXES, default="X")
    first_offset: bpy.props.FloatProperty(
        name="First Position", description="Degrees or millimeters from where the object stands", default=-20.0
    )
    offset_step: bpy.props.FloatProperty(
        name="Step", description="Degrees or millimeters from one position to the next", default=40.0
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "dataref")
        row = layout.row()
        row.prop(self, "positions")
        row.prop(self, "replace")
        row = layout.row(align=True)
        row.prop(self, "first_value")
        row.prop(self, "value_step")
        row = layout.row()
        row.prop(self, "motion", expand=True)
        row.prop(self, "axis", text="")
        unit = "°" if self.motion == "ROTATE" else " mm"
        row = layout.row(align=True)
        row.prop(self, "first_offset", text=f"First Position ({unit.strip()})")
        row.prop(self, "offset_step", text=f"Step ({unit.strip()})")
        values = [self.first_value + i * self.value_step for i in range(self.positions)]
        offsets = [self.first_offset + i * self.offset_step for i in range(self.positions)]
        layout.label(text="   ".join(f"{v:g} → {o:g}{unit}" for v, o in zip(values, offsets)), icon="INFO")

    def execute(self, context):
        scale = math.radians(1.0) if self.motion == "ROTATE" else 0.001
        values = [self.first_value + i * self.value_step for i in range(self.positions)]
        offsets = [(self.first_offset + i * self.offset_step) * scale for i in range(self.positions)]
        done, skipped = 0, []
        for obj in context.selected_objects:
            dataref = fill_name(self.dataref, obj).strip()
            if not dataref and obj.xplane.manip.enabled:
                dataref = obj.xplane.manip.dataref1
            reason = animate(obj, dataref, values, offsets, self.motion, self.axis, replace=self.replace)
            if reason:
                skipped.append((obj.name, reason))
            else:
                done += 1
        return self.finish(done, skipped)


class XPLANE_OT_anim_range(_Preset, bpy.types.Operator):
    """Animate the selected objects as knobs, levers or sliders that follow a dataref over a range"""

    bl_idname = "xplane.anim_range"
    bl_label = "Knob / Lever"
    bl_options = {"REGISTER", "UNDO"}

    dataref: bpy.props.StringProperty(
        name="Dataref",
        description="The dataref the control follows. Empty uses each object's manipulator dataref. {name} becomes the object's name",
    )
    value_from: bpy.props.FloatProperty(name="From Value", default=0.0)
    value_to: bpy.props.FloatProperty(name="To Value", default=1.0)
    motion: bpy.props.EnumProperty(name="Motion", items=MOTIONS, default="ROTATE")
    axis: bpy.props.EnumProperty(name="Axis", items=AXES, default="Z")
    offset_from: bpy.props.FloatProperty(name="From", description="Degrees or millimeters", default=-135.0)
    offset_to: bpy.props.FloatProperty(name="To", description="Degrees or millimeters", default=135.0)
    loop: bpy.props.FloatProperty(
        name="Loop Every",
        description="For endless knobs: the animation repeats every this much of the dataref. 0 for none",
        default=0.0,
        min=0.0,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "dataref")
        row = layout.row(align=True)
        row.prop(self, "value_from")
        row.prop(self, "value_to")
        row = layout.row()
        row.prop(self, "motion", expand=True)
        row.prop(self, "axis", text="")
        unit = "°" if self.motion == "ROTATE" else "mm"
        row = layout.row(align=True)
        row.prop(self, "offset_from", text=f"From ({unit})")
        row.prop(self, "offset_to", text=f"To ({unit})")
        row = layout.row()
        row.prop(self, "loop")
        row.prop(self, "replace")

    def execute(self, context):
        scale = math.radians(1.0) if self.motion == "ROTATE" else 0.001
        done, skipped = 0, []
        for obj in context.selected_objects:
            dataref = fill_name(self.dataref, obj).strip()
            if not dataref and obj.xplane.manip.enabled:
                dataref = obj.xplane.manip.dataref1
            reason = animate(
                obj,
                dataref,
                (self.value_from, self.value_to),
                (self.offset_from * scale, self.offset_to * scale),
                self.motion,
                self.axis,
                loop=self.loop,
                replace=self.replace,
            )
            if reason:
                skipped.append((obj.name, reason))
            else:
                done += 1
        return self.finish(done, skipped)


class VIEW3D_PT_xplane_animate(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "X-Plane"
    bl_label = "Animate"

    def draw(self, context):
        col = self.layout.column(align=True)
        col.scale_y = 1.2
        col.operator(XPLANE_OT_anim_push_button.bl_idname, icon="TRIA_DOWN_BAR")
        col.operator(XPLANE_OT_anim_switch.bl_idname, icon="SNAP_INCREMENT")
        col.operator(XPLANE_OT_anim_range.bl_idname, icon="DRIVER_ROTATIONAL_DIFFERENCE")
        self.layout.label(text=f"{len(context.selected_objects)} selected object(s)")


_classes = (XPLANE_OT_anim_push_button, XPLANE_OT_anim_switch, XPLANE_OT_anim_range, VIEW3D_PT_xplane_animate)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
