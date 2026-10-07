"""
test_creation_tools

These allow the quick automated setup of test cases

- get_ get's a Blender datablock or piece of data or None
- set_ set's some data, possibly creating data as needed.
- create_ creates and returns exist Blender data, or returns existing data with the same name
- delete_ deletes all of a certain type from the scene

This also is a wrapper around Blender's more confusing aspects of it's API and datamodel.
https://blender.stackexchange.com/questions/6101/poll-failed-context-incorrect-example-bpy-ops-view3d-background-image-add
"""

import math
import os.path
import shutil
import typing
from collections import namedtuple
from pathlib import Path
from typing import *

import bpy
from mathutils import Euler, Quaternion, Vector

import io_xplane2blender
from io_xplane2blender import xplane_constants, xplane_helpers
from io_xplane2blender.xplane_constants import ANIM_TYPE_HIDE, ANIM_TYPE_SHOW
from io_xplane2blender.xplane_helpers import (
    ExportableRoot,
    PotentialRoot,
    XPlaneLogger,
    logger,
)
from io_xplane2blender.xplane_props import XPlaneManipulatorSettings
from io_xplane2blender.xplane_types import xplane_file

# Most used commands:
#
#

# Most used datarefs:
#
# - sim/cockpit2/engine/actuators/throttle_ratio_all    float    y    ratio    Throttle position of the handle itself - this controls all the handles at once.
# - sim/graphics/animation/sin_wave_2    float    n    ratio    -1 to 1

# Most used named/param lights
# area_lt_param_sp
# 0 -1 0    75
# spot_params_bb
# 1 1 1 1.0 2.121 0 2.121 -2
# spot_params_sp
# 0 .2 1    20 30   0 -1  0   1

# Rotations, when in euler's, are in angles, and get transformed when they need to.

from .test_creation_infos import *
from .test_creation_datablocks import *
from .test_setting_helpers import *
