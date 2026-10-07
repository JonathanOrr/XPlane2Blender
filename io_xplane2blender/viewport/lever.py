"""
The lever handle: a gizmo on the active animated object to drag it through its animation the way it moves in X-Plane.
A turning part (knob, lever, door) gets a dial around its hinge, a sliding part (throttle, seat, window) an arrow
along its slide. Dragging changes the scene frame, which poses the part between its keyframes, and the overlay says
the dataref value there. Nothing is keyed or changed.
"""

import math
from typing import Tuple

import bpy
from mathutils import Matrix

from . import draw
from .motion import TURN, motion_of
from .overlay_more import hub_and_arm
from .settings import view_settings

COLOR = (1.0, 0.8, 0.2)
HIGHLIGHT = (1.0, 1.0, 0.6)


def set_frame(scene: bpy.types.Scene, frame: float) -> None:
    whole = math.floor(frame)
    scene.frame_set(int(whole), subframe=frame - whole)


def turn_matrix(obj: bpy.types.Object, motion) -> Tuple[Matrix, float]:
    """
    Dial placement: at the hub, Y (where Blender's dial counts angles from) pointing to where the part is at the
    first keyframe, and Z against the hinge axis, as the dial counts clockwise
    """
    hub, arm = hub_and_arm(obj, motion)
    start = Matrix.Rotation(-motion.now, 3, motion.axis) @ arm
    y = start.normalized()
    z = -motion.axis.normalized()
    x = y.cross(z)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = hub
    return m, start.length


def ahead(obj: bpy.types.Object) -> float:
    """How far ahead of the part's middle the arrow's head is, to be outside the part"""
    return max(max(obj.dimensions) * 0.8, 0.005)


def slide_matrix(obj: bpy.types.Object, motion) -> Matrix:
    """
    Arrow placement: Z along the slide. The arrow grows from here to its head as the part slides, so this is where
    the head is at the first keyframe: ahead of the part's middle
    """
    m = motion.axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
    m.translation = draw.box_center(obj) + motion.axis * (ahead(obj) - motion.now)
    return m


class XPLANE_GGT_lever(bpy.types.GizmoGroup):
    bl_idname = "XPLANE_GGT_lever"
    bl_label = "X-Plane Lever Handle"
    bl_space_type = "VIEW_3D"
    bl_region_type = "WINDOW"
    bl_options = {"3D", "PERSISTENT", "SHOW_MODAL_ALL"}

    @classmethod
    def poll(cls, context):
        s = view_settings(context)
        return bool(s and s.show_lever and context.mode == "OBJECT" and motion_of(context.object) is not None)

    def _motion(self):
        return motion_of(bpy.context.object)

    def _handlers(self, unit):
        """
        Gizmo offset <-> travel: the dial's offset is the angle itself, the arrow's is in arrow lengths. Dragging
        past either end stops at the end keyframe
        """

        def get():
            motion = self._motion()
            return motion.now / unit() if motion else 0.0

        def set(value):
            motion = self._motion()
            if motion is not None:
                set_frame(bpy.context.scene, motion.frame_at(value * unit()))

        def limits():
            motion = self._motion()
            if motion is None or motion.high <= motion.low:
                return 0.0, 1.0
            return motion.low / unit(), motion.high / unit()

        return {"get": get, "set": set, "range": limits}

    def setup(self, context):
        self.arrow_length = 1.0
        self.dial = self.gizmos.new("GIZMO_GT_dial_3d")
        self.dial.draw_options = {"ANGLE_VALUE"}
        self.dial.target_set_handler("offset", **self._handlers(lambda: 1.0))
        self.arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
        self.arrow.target_set_handler("offset", **self._handlers(lambda: self.arrow_length))
        for gizmo in (self.dial, self.arrow):
            gizmo.color, gizmo.alpha = COLOR, 0.7
            gizmo.color_highlight, gizmo.alpha_highlight = HIGHLIGHT, 1.0
            gizmo.use_draw_value = True
            # Sized in the scene, not on screen. Gizmos ignore scale_basis then, so the size is in their matrix
            gizmo.use_draw_scale = False
        self.refresh(context)

    def refresh(self, context):
        obj = context.object
        motion = motion_of(obj)
        if motion is None:
            return
        turning = motion.kind == TURN
        self.dial.hide, self.arrow.hide = not turning, turning
        if turning:
            matrix, radius = turn_matrix(obj, motion)
            self.dial.matrix_basis = matrix @ Matrix.Scale(max(radius, 0.005), 4)
        else:
            self.arrow_length = max((motion.high - motion.low) * 0.3, 0.005)
            self.arrow.matrix_basis = slide_matrix(obj, motion) @ Matrix.Scale(self.arrow_length, 4)


classes = (XPLANE_GGT_lever,)
