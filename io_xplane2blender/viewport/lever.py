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
    """Dial placement: at the hub, Z along the hinge, X pointing to where the part is at the first keyframe"""
    hub, arm = hub_and_arm(obj, motion)
    start = Matrix.Rotation(-motion.now, 3, motion.axis) @ arm
    x = start.normalized()
    z = motion.axis.normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = hub
    return m, start.length


def slide_matrix(obj: bpy.types.Object, motion) -> Matrix:
    """Arrow placement: where the part's middle is at the first keyframe, Z along the slide"""
    m = motion.axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
    m.translation = draw.box_center(obj) - motion.axis * motion.now
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

    def _get(self):
        motion = self._motion()
        return motion.now if motion else 0.0

    def _set(self, value):
        motion = self._motion()
        if motion is not None:
            set_frame(bpy.context.scene, motion.frame_at(value))

    def _range(self):
        motion = self._motion()
        return (motion.low, motion.high) if motion and motion.high > motion.low else (0.0, 1.0)

    def setup(self, context):
        self.dial = self.gizmos.new("GIZMO_GT_dial_3d")
        self.dial.draw_options = {"ANGLE_VALUE"}
        self.arrow = self.gizmos.new("GIZMO_GT_arrow_3d")
        self.arrow.transform = {"CONSTRAIN"}
        for gizmo in (self.dial, self.arrow):
            gizmo.target_set_handler("offset", get=self._get, set=self._set, range=self._range)
            gizmo.color, gizmo.alpha = COLOR, 0.7
            gizmo.color_highlight, gizmo.alpha_highlight = HIGHLIGHT, 1.0
            gizmo.use_draw_value = True
        self.refresh(context)

    def refresh(self, context):
        obj = context.object
        motion = motion_of(obj)
        if motion is None:
            return
        turning = motion.kind == TURN
        self.dial.hide, self.arrow.hide = not turning, turning
        if turning:
            self.dial.matrix_basis, radius = turn_matrix(obj, motion)
            self.dial.use_draw_scale = False
            self.dial.scale_basis = max(radius, 0.005)
        else:
            self.arrow.matrix_basis = slide_matrix(obj, motion)
            self.arrow.use_draw_scale = False
            self.arrow.scale_basis = max(motion.high - motion.low, 0.005)


classes = (XPLANE_GGT_lever,)

