"""
Click and drag settings: what a part does when it is clicked, dragged or scrolled in the cockpit.
"""

import bpy

from io_xplane2blender.xplane_constants import *

from .common import XPlaneAxisDetentRange

# Blender saves the position in this list, so it must only ever be added to at the end
MANIP_TYPE_ITEMS = [
    (MANIP_DRAG_XY, "Drag XY", "Drag XY"),
    (MANIP_DRAG_AXIS, "Drag Axis", "Drag Axis"),
    (MANIP_COMMAND, "Command", "Command"),
    (MANIP_COMMAND_AXIS, "Command Axis", "Command Axis"),
    (MANIP_PUSH, "Push", "Push"),
    (MANIP_RADIO, "Radio", "Radio"),
    (MANIP_DELTA, "Delta", "Delta"),
    (MANIP_WRAP, "Wrap", "Wrap"),
    (MANIP_TOGGLE, "Toggle", "Toggle"),
    (MANIP_NOOP, "No-op", "No-op"),
    (MANIP_DRAG_AXIS_PIX, "Drag Axis Pix", "Drag Axis Pix"),
    (MANIP_COMMAND_KNOB, "Command Knob", "Command Knob"),
    (MANIP_COMMAND_SWITCH_UP_DOWN, "Command Switch Up Down", "Command Switch Up Down"),
    (MANIP_COMMAND_SWITCH_LEFT_RIGHT, "Command Switch Left Right", "Command Switch Left Right"),
    (MANIP_AXIS_SWITCH_UP_DOWN, "Axis Switch Up Down", "Axis Switch Up Down"),
    (MANIP_AXIS_SWITCH_LEFT_RIGHT, "Axis Switch Left Right", "Axis Switch Left Right"),
    (MANIP_AXIS_KNOB, "Axis Knob", "Axis Knob"),
    (MANIP_DRAG_AXIS_DETENT, "Drag Axis With Detents", "Drag Axis With Detents"),
    (MANIP_COMMAND_KNOB2, "Command Knob 2", "Command Knob 2"),
    (MANIP_COMMAND_SWITCH_UP_DOWN2, "Command Switch Up Down 2", "Command Switch Up Down 2"),
    (MANIP_COMMAND_SWITCH_LEFT_RIGHT2, "Command Switch Left Right 2", "Command Switch Left Right 2"),
    (MANIP_DRAG_ROTATE, "Drag Rotate", "Drag Rotate"),
    (MANIP_DRAG_ROTATE_DETENT, "Drag Rotate With Detents", "Drag Rotate With Detents"),
    (MANIP_DEVICE, "Device", "Device"),
]

CURSOR_ITEMS = [
    (MANIP_CURSOR_FOUR_ARROWS, "Four Arrows", "Four Arrows"),
    (MANIP_CURSOR_HAND, "Hand", "Hand"),
    (MANIP_CURSOR_BUTTON, "Button", "Button"),
    (MANIP_CURSOR_ROTATE_SMALL, "Rotate Small", "Rotate Small"),
    (MANIP_CURSOR_ROTATE_SMALL_LEFT, "Rotate Small Left", "Rotate Small Left"),
    (MANIP_CURSOR_ROTATE_SMALL_RIGHT, "Rotate Small Right", "Rotate Small Right"),
    (MANIP_CURSOR_ROTATE_MEDIUM, "Rotate Medium", "Rotate Medium"),
    (MANIP_CURSOR_ROTATE_MEDIUM_LEFT, "Rotate Medium Left", "Rotate Medium Left"),
    (MANIP_CURSOR_ROTATE_MEDIUM_RIGHT, "Rotate Medium Right", "Rotate Medium Right"),
    (MANIP_CURSOR_ROTATE_LARGE, "Rotate Large", "Rotate Large"),
    (MANIP_CURSOR_ROTATE_LARGE_LEFT, "Rotate Large Left", "Rotate Large Left"),
    (MANIP_CURSOR_ROTATE_LARGE_RIGHT, "Rotate Large Right", "Rotate Large Right"),
    (MANIP_CURSOR_UP_DOWN, "Up Down", "Up Down"),
    (MANIP_CURSOR_DOWN, "Down", "Down"),
    (MANIP_CURSOR_UP, "Up", "Up"),
    (MANIP_CURSOR_LEFT_RIGHT, "Left Right", "Left Right"),
    (MANIP_CURSOR_LEFT, "Left", "Left"),
    (MANIP_CURSOR_RIGHT, "Right", "Right"),
    (MANIP_CURSOR_ARROW, "Arrow", "Arrow"),
]


def _value(name: str, description: str, default: float = 0.0):
    return bpy.props.FloatProperty(name=name, description=description, default=default, precision=3)


class XPlaneManipulatorSettings(bpy.types.PropertyGroup):
    autodetect_datarefs: bpy.props.BoolProperty(
        name="Autodetect Datarefs",
        description="Use the datarefs the object's animation is keyed on, instead of typing them in",
        default=True,
    )
    # This is meant for making old manipulator types smarter, not new manipulator types
    autodetect_settings_opt_in: bpy.props.BoolProperty(
        name="Autodetect Settings",
        description="Take the drag direction and the dataref values from the object's animation, instead of typing them in",
        default=False,
    )
    axis_detent_ranges: bpy.props.CollectionProperty(
        name="Axis Detent Range",
        description="The ranges where a drag rotate manipulator can move freely, and what heights must be overcome to enter each range",
        type=XPlaneAxisDetentRange,
    )
    enabled: bpy.props.BoolProperty(
        name="Manipulator", description="Make the object clickable in X-Plane", default=False
    )
    type: bpy.props.EnumProperty(
        name="Manipulator Type", description="What clicking or dragging the object does", items=MANIP_TYPE_ITEMS
    )
    tooltip: bpy.props.StringProperty(
        name="Manipulator Tooltip", description="The text X-Plane shows while the mouse is over the object"
    )
    cursor: bpy.props.EnumProperty(
        name="Manipulator Cursor",
        description="The mouse cursor X-Plane shows over the object",
        default=MANIP_CURSOR_HAND,
        items=CURSOR_ITEMS,
    )
    dx: _value(
        "Drag X",
        "How far the drag goes: along X in meters for a slide or Drag runs commands, the width of Drag in two"
        " directions, or the pixels of Drag the mouse sideways",
    )
    dy: _value(
        "Drag Y",
        "How far the drag goes: along Y in meters for a slide or Drag runs commands, or the height of Drag in two"
        " directions",
    )
    dz: _value("Drag Z", "How far the drag goes along Z, in meters, for a slide or Drag runs commands")
    v1: _value("Value 1", "The dataref value at the start of the drag, or the lowest value of a stepped switch or knob")
    v2: _value("Value 2", "The dataref value at the end of the drag, or the highest value of a stepped switch or knob")
    v1_min: _value(
        "Value 1 Min", "The lowest value of a Step, or where the left / right dataref starts in Drag in two directions"
    )
    v1_max: _value(
        "Value 1 Max", "The highest value of a Step, or where the left / right dataref ends in Drag in two directions"
    )
    v2_min: _value(
        "Value 2 Min",
        "Where the up / down dataref starts in Drag in two directions, or the detent dataref with the lever at rest",
    )
    v2_max: _value(
        "Value 2 Max",
        "Where the up / down dataref ends in Drag in two directions, or the detent dataref with the lever lifted",
    )
    detent_dataref_range: bpy.props.BoolProperty(
        name="Own Detent Dataref Range",
        description="The detent dataref goes from its value at rest to its value lifted as the lever is lifted"
        " (Laminar's levers use 0 to 1), and the detent heights are in its units. Off: it goes from 0 to the lift in"
        " meters",
        default=False,
    )
    v_down: _value(
        "Value On Mouse Down",
        "The value the dataref is set to when the object is clicked (and held, for Push), or added on each click for"
        " a Step",
    )
    v_up: _value("Value On Mouse Up", "The value the dataref is set to when the mouse is released")
    v_hold: _value("Value On Mouse Hold", "The value added to the dataref while the mouse is held down")
    v_on: _value("On Value", "The dataref value when the toggle is on")
    v_off: _value("Off Value", "The dataref value when the toggle is off")
    command: bpy.props.StringProperty(name="Command", description="The command X-Plane runs when the object is clicked (for a Button, while it is held)")
    positive_command: bpy.props.StringProperty(name="Positive Command", description="The command for one way: clockwise, up, right or forward")
    negative_command: bpy.props.StringProperty(name="Negative Command", description="The command for the other way: counter-clockwise, down, left or back")
    dataref1: bpy.props.StringProperty(
        name="Dataref 1", description="The dataref the control changes (the left / right one in Drag in two directions)"
    )
    dataref2: bpy.props.StringProperty(
        name="Dataref 2",
        description="The second dataref: the up / down one in Drag in two directions, or the one the lever is lifted by"
        " for detents",
    )
    device_name: bpy.props.EnumProperty(
        name="Device",
        description="The avionics device whose touch screen gets the clicks. The mesh must have the shape and UVs of"
        " the device's screen",
        default=DEVICE_GNS430_1,
        items=[(device, device, device) for device in DEVICES],
    )
    noop_label: bpy.props.StringProperty(
        name="Label Dataref",
        description="A dataref written after a click blocker, as Laminar do to tell which instrument it covers."
        " X-Plane ignores it",
    )
    plugin_device: bpy.props.StringProperty(
        name="Device ID", description="The device ID your plugin created the avionics device with"
    )
    step: _value("Step", "The dataref changes in steps of this size", 1.0)
    click_step: _value("Click Step", "How much each click changes the dataref")
    hold_step: _value("Hold Step", "How much the dataref changes while the mouse is held down")
    wheel_delta: _value("Wheel Delta", "How much one click of the mouse wheel changes the dataref. 0: the wheel does nothing")
    exp: _value(
        "Exp",
        "How the dataref speeds up with the drag: higher numbers make small drags precise and large drags fast."
        " 1: even",
        1.0,
    )

    def get_effective_type_name(self) -> str:
        """The name shown in the UI"""
        return next(name for identifier, name, _ in MANIP_TYPE_ITEMS if identifier == self.type)
