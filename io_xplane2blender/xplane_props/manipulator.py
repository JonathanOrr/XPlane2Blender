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
        description="If checked, dataref(s) for this manipulator will be taken from its mesh's animations",
        default=True,
    )
    # This is meant for making old manipulator types smarter, not new manipulator types
    autodetect_settings_opt_in: bpy.props.BoolProperty(
        name="Autodetect Settings",
        description="Use new algorithms to autodetect certain manipulator settings from animation data",
        default=False,
    )
    axis_detent_ranges: bpy.props.CollectionProperty(
        name="Axis Detent Range",
        description="The ranges where a drag rotate manipulator can move freely, and what heights must be overcome to enter each range",
        type=XPlaneAxisDetentRange,
    )
    enabled: bpy.props.BoolProperty(
        name="Manipulator", description="If checked, this object will be treated as a manipulator", default=False
    )
    type: bpy.props.EnumProperty(
        name="Manipulator Type", description="The type of the manipulator", items=MANIP_TYPE_ITEMS
    )
    tooltip: bpy.props.StringProperty(
        name="Manipulator Tooltip", description="The tooltip will be displayed when hovering over the object"
    )
    cursor: bpy.props.EnumProperty(
        name="Manipulator Cursor",
        description="The mouse cursor type when hovering over the object",
        default=MANIP_CURSOR_HAND,
        items=CURSOR_ITEMS,
    )
    dx: _value("Drag X", "X-Drag axis length")
    dy: _value("Drag Y", "Y-Drag axis length")
    dz: _value("Drag Z", "Z-Drag axis length")
    v1: _value("Value 1", "Value 1")
    v2: _value("Value 2", "Value 2")
    v1_min: _value("Value 1 Min", "Value 1 min")
    v1_max: _value("Value 1 Max", "Value 1 max")
    v2_min: _value("Value 2 Min", "Value 2 min")
    v2_max: _value("Value 2 Max", "Value 2 max")
    v_down: _value("Value On Mouse Down", "Value to set dataref on mouse down")
    v_up: _value("Value On Mouse Up", "Value to set dataref on mouse up")
    v_hold: _value("Value On Mouse Hold", "Value to set dataref on mouse hold")
    v_on: _value("On Value", "On value")
    v_off: _value("Off Value", "Off value")
    command: bpy.props.StringProperty(name="Command", description="The command to fire when manipulator is used")
    positive_command: bpy.props.StringProperty(name="Positive Command", description="Positive command")
    negative_command: bpy.props.StringProperty(name="Negative Command", description="Negative command")
    dataref1: bpy.props.StringProperty(name="Dataref 1", description="Dataref 1")
    dataref2: bpy.props.StringProperty(name="Dataref 2", description="Dataref 2")
    step: _value("Step", "Dataref increment", 1.0)
    click_step: _value("Click Step", "Value change on click")
    hold_step: _value("Hold Step", "Value change on hold")
    wheel_delta: _value("Wheel Delta", "Value change on mouse wheel tick")
    exp: _value(
        "Exp",
        "Power of an exponential curve that controls the speed at which the dataref changes. Higher numbers cause a"
        " more “non-linear” response, where small drags are very precise and large drags are very fast",
        1.0,
    )

    def get_effective_type_name(self) -> str:
        """The name shown in the UI"""
        return next(name for identifier, name, _ in MANIP_TYPE_ITEMS if identifier == self.type)
