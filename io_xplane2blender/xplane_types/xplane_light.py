from dataclasses import dataclass
from itertools import chain
from typing import List, Optional

import bpy
from mathutils import Vector

from io_xplane2blender.xplane_types import xplane_object
from io_xplane2blender.xplane_utils import xplane_lights_txt_parser

from ..xplane_constants import *
from ..xplane_helpers import floatToStr, unfinished
from .xplane_light_collect import (
    XPlaneLightCollect,
    dir_mag_for_billboard,
    width_for_billboard,
    width_for_spill,
)
from .xplane_light_write import XPlaneLightWrite


@dataclass
class _LightSpillCustomParams:
    r: float
    g: float
    b: float

    @property
    def a(self):
        return 1

    size: float
    dx: float
    dy: float
    dz: float
    width: float
    dataref: str

    def __str__(self):
        return " ".join(
            chain(
                map(
                    floatToStr,
                    (
                        self.r,
                        self.g,
                        self.b,
                        self.a,
                        self.size,
                        self.dx,
                        self.dy,
                        self.dz,
                        self.width,
                    ),
                ),
                (self.dataref,),
            )
        )


class XPlaneLight(XPlaneLightCollect, XPlaneLightWrite, xplane_object.XPlaneObject):
    def __init__(self, blenderObject: bpy.types.Object):
        super().__init__(blenderObject)

        # Our light type, not the Blender light type
        self.lightType = blenderObject.data.xplane.type

        # Color, for use by CUSTOM or AUTOMATIC lights
        if blenderObject.data.xplane.enable_rgb_override:
            self.color: List[float] = blenderObject.data.xplane.rgb_override_values[:]
        else:
            self.color: List[float] = list(blenderObject.data.color)

        self.dataref = blenderObject.data.xplane.dataref
        self.energy = blenderObject.data.energy
        # The Size of a Custom Light
        # and the SIZE replacement for an Automatic Light
        self.size = blenderObject.data.xplane.size
        self.uv = blenderObject.data.xplane.uv

        # Our lights.txt light name, not the Blender Object's name
        self.lightName = blenderObject.data.xplane.name.strip()

        # If the lightName is unknown
        #     params_completed and record_completed these will be none
        # Use __getitem__ and __contains__ to ask if there are columns
        # and fields we care about

        # self.params is the eventual content of the
        # LIGHT_PARAM OBJ directive
        if self.lightType == LIGHT_AUTOMATIC:
            self.params = {}
        elif self.lightType == LIGHT_PARAM:
            self.params = blenderObject.data.xplane.params
        elif self.lightType == LIGHT_SPILL_CUSTOM:
            self.params = _LightSpillCustomParams(*([0] * 8), "")
        else:
            self.params = None

        # Possible comment extracted from a param light params text field
        self.comment: Optional[str] = None

        # If applicable, after collection this will be
        # the light's best overload with any parameters replaced
        # and any sw_callbacks, ready for autocorrection
        self.record_completed: Optional[
            xplane_lights_txt_parser.ParsedLightOverload
        ] = None

        self.setWeight(10000)

    def collect(self) -> None:
        super().collect()

        if self.lightType == LIGHT_NON_EXPORTING:
            return
        elif not self.lightName and self.lightType in {
            LIGHT_NAMED,
            LIGHT_PARAM,
            LIGHT_AUTOMATIC,
        }:
            # Unfinished work, not an error: the light is left out and the rest of the file exports
            unfinished.add(
                "lights without an X-Plane light chosen", self.blenderObject.name
            )
            self.lightType = LIGHT_NON_EXPORTING
            return
        try:
            parsed_light = xplane_lights_txt_parser.get_parsed_light(self.lightName)
        except KeyError:
            parsed_light = None

        if self.lightType == LIGHT_NAMED:
            self._collect_named(parsed_light)
        elif self.lightType == LIGHT_PARAM:
            self._collect_param(parsed_light)
        elif self.lightType == LIGHT_CUSTOM:
            pass  # Written as is
        elif self.lightType == LIGHT_AUTOMATIC:
            self._collect_automatic(parsed_light)
        elif self.lightType == LIGHT_SPILL_CUSTOM:
            self._collect_spill_custom()
        else:
            assert (
                False
            ), f"{self.blenderObject.name} had some property configuation that was unaccounted for"

    def get_light_direction_b(self) -> Vector:
        """
        Returns a unit vector the light's direction,
        even if the light is a POINT light.

        Must be called after self.xplaneBone has been assaigned
        """
        bakeMatrix = self.xplaneBone.getBakeMatrixForAttached()
        dir_vec_b_norm = (bakeMatrix.to_3x3() @ Vector((0, 0, -1))).normalized()
        return dir_vec_b_norm

    DIR_MAG_for_billboard = staticmethod(dir_mag_for_billboard)
    WIDTH_for_billboard = staticmethod(width_for_billboard)
    WIDTH_for_spill = staticmethod(width_for_spill)
