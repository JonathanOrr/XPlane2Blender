"""
The motion overlay and the lever handle: how an animated object turns or slides is read from its keyframes
(drawing needs a window, so only the geometry is checked)
"""

import math
from types import SimpleNamespace

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants as C
from io_xplane2blender.tests import *
from io_xplane2blender.tests import test_creation_helpers
from io_xplane2blender.viewport import lever, overlay_more
from io_xplane2blender.viewport.motion import SLIDE, TURN, interpolate, motion_of


def animated(name, keys, channel="rotation_euler", location=(0, 0, 0), parent=None):
    """keys: (frame, dataref value, channel value)"""
    obj = test_creation_helpers.create_datablock_mesh(
        test_creation_helpers.DatablockInfo("MESH", name, location=location)
    )
    if parent is not None:
        obj.parent = parent
    dataref = obj.xplane.datarefs.add()
    dataref.path, dataref.anim_type = f"a321/{name}", C.ANIM_TYPE_TRANSFORM
    for frame, value, pose in keys:
        dataref.value = value
        obj.keyframe_insert("xplane.datarefs[0].value", frame=frame)
        setattr(obj, channel, pose)
        obj.keyframe_insert(channel, frame=frame)
    for fcurve in test_creation_helpers.xplane_helpers.get_action_fcurves(obj):
        for key in fcurve.keyframe_points:
            key.interpolation = "LINEAR"
    bpy.context.scene.frame_set(int(keys[0][0]))
    return obj


class TestViewportMotion(XPlaneTestCase):
    def setUp(self):
        super().setUp()
        test_creation_helpers.delete_everything()

    def test_a_lever_turns_around_its_origin(self) -> None:
        obj = animated(
            "lever",
            ((1, 0.0, (0, 0, 0)), (2, 1.0, (math.radians(90), 0, 0))),
            location=(1, 2, 3),
        )
        motion = motion_of(obj)
        self.assertEqual(TURN, motion.kind)
        self.assertEqual("a321/lever", motion.dataref)
        self.assertAlmostEqual(math.pi / 2, motion.travel[-1], places=4)
        self.assertAlmostEqual(1.0, abs(motion.axis.dot(Vector((1, 0, 0)))), places=4)
        self.assertLess((motion.origin - Vector((1, 2, 3))).length, 1e-5)
        self.assertAlmostEqual(1.5, motion.frame_at(math.pi / 4), places=4)
        self.assertAlmostEqual(0.5, motion.value_at(math.pi / 4), places=4)
        self.assertAlmostEqual(0.0, motion.now)

    def test_a_knob_turning_past_half_a_turn_keeps_counting(self) -> None:
        keys = [(1 + i, i / 3, (0, 0, math.radians(120 * i))) for i in range(4)]
        motion = motion_of(animated("knob", keys))
        self.assertEqual(TURN, motion.kind)
        self.assertAlmostEqual(2 * math.pi, abs(motion.travel[-1]), places=3)

    def test_a_throttle_slides_and_parent_scale_counts(self) -> None:
        parent = bpy.data.objects.new("pedestal", None)
        bpy.context.scene.collection.objects.link(parent)
        parent.scale = (2, 2, 2)
        obj = animated(
            "throttle",
            ((1, 0.0, (0, 0, 0)), (3, 1.0, (0, 0.1, 0))),
            channel="location",
            parent=parent,
        )
        bpy.context.view_layer.update()
        motion = motion_of(obj)
        self.assertEqual(SLIDE, motion.kind)
        self.assertAlmostEqual(0.2, motion.travel[-1], places=4)
        self.assertAlmostEqual(1.0, motion.axis.dot(Vector((0, 1, 0))), places=4)
        bpy.context.scene.frame_set(2)
        self.assertAlmostEqual(0.1, motion_of(obj).now, places=4)

    def test_still_parts_have_no_motion(self) -> None:
        self.assertIsNone(motion_of(None))
        obj = test_creation_helpers.create_datablock_mesh(
            test_creation_helpers.DatablockInfo("MESH", "still")
        )
        self.assertIsNone(motion_of(obj))
        self.assertIsNone(
            motion_of(animated("stuck", ((1, 0.0, (0, 0, 0)), (2, 1.0, (0, 0, 0)))))
        )

    def test_interpolate_clamps_and_reads_there_and_back(self) -> None:
        self.assertEqual(0.0, interpolate(-5, [0, 10], [0, 1]))
        self.assertEqual(1.0, interpolate(50, [0, 10], [0, 1]))
        self.assertAlmostEqual(0.25, interpolate(2.5, [10, 0], [0, 1]) - 0.5)
        self.assertAlmostEqual(0.5, interpolate(5, [0, 10, 0], [0, 1, 2]))

    def test_motion_path_and_lever_placement(self) -> None:
        obj = animated(
            "door",
            ((1, 0.0, (0, 0, 0)), (2, 1.0, (0, 0, math.radians(90)))),
            location=(0, 0, 0),
        )
        obj.data.transform(__import__("mathutils").Matrix.Translation((1, 0, 0)))
        bpy.context.view_layer.update()
        motion = motion_of(obj)
        path, keys, hinge = overlay_more.motion_shape(obj, motion)
        self.assertLess((keys[0] - Vector((1, 0, 0))).length, 1e-4)
        self.assertLess((keys[1] - Vector((0, 1, 0))).length, 1e-4)
        self.assertEqual(2, len(hinge))
        matrix, radius = lever.turn_matrix(obj, motion)
        self.assertAlmostEqual(1.0, radius, places=4)
        # The dial counts from its Y axis, which points at the part at the first keyframe
        self.assertLess((matrix.col[1].xyz - Vector((1, 0, 0))).length, 1e-4)

    def test_lever_handle_shows_only_when_asked_for_an_animated_part(self) -> None:
        obj = animated(
            "flap", ((1, 0.0, (0, 0, 0)), (2, 1.0, (0, math.radians(30), 0)))
        )
        screen = bpy.data.screens[0]
        context = SimpleNamespace(screen=screen, mode="OBJECT", object=obj)
        screen.xplane_view.show_lever = False
        self.assertFalse(lever.XPLANE_GGT_lever.poll(context))
        screen.xplane_view.show_lever = True
        self.assertTrue(lever.XPLANE_GGT_lever.poll(context))
        self.assertFalse(
            lever.XPLANE_GGT_lever.poll(
                SimpleNamespace(screen=None, mode="OBJECT", object=obj)
            )
        )
        lever.set_frame(bpy.context.scene, 1.5)
        self.assertEqual(
            (1, 0.5),
            (bpy.context.scene.frame_current, bpy.context.scene.frame_subframe),
        )

    def test_lights_and_unfinished_overlays(self) -> None:
        data = bpy.data.lights.new("beacon", "POINT")
        data.color = (1, 0, 0)
        data.xplane.type = C.LIGHT_AUTOMATIC
        obj = bpy.data.objects.new("beacon", data)
        bpy.context.scene.collection.objects.link(obj)
        self.assertIsNone(overlay_more.light_name(data))
        data.xplane.name = "airplane_beacon"
        self.assertEqual("airplane_beacon", overlay_more.light_name(data))
        self.assertEqual((1, 0, 0, 1), overlay_more.light_color(data))
        self.assertEqual([obj], overlay_more.x_plane_lights(bpy.context))
        data.xplane.type = C.LIGHT_NON_EXPORTING
        self.assertEqual([], overlay_more.x_plane_lights(bpy.context))
        item = bpy.context.window_manager.xplane_panels.check_items.add()
        item.object_name, item.text = "beacon", "No light chosen"
        self.assertEqual(
            [(obj, "No light chosen")], overlay_more.unfinished_objects(bpy.context)
        )
        bpy.context.window_manager.xplane_panels.check_items.clear()


runTestCases([TestViewportMotion])
