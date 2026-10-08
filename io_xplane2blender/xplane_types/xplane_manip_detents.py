"""
Checks the detent ranges of a drag manipulator with detents.

Rules for Axis Detent Ranges

Basic rules
- Manip type must be *_DETENT
- Translation bone must not be none (covered by get_translation_bone), len(axis_detent_ranges) > 0
- The detent ranges must cover [v1_min,v1_max] without gaps.
  Therefore
      - The start of one range must be the end of another
      - ranges[0].start == v1_min, ranges[-1].end == v1_max
- A range's start must be <= its end
- Height must be between the values of dataref 2 at the bottom and top of the lift

Stop Pits
- A stop pit is defined as range.start == range.end, range.height is not higher than either of its neighbors.
- A pit can be the first or last detent range, but never the only one
- Stop pegs, where height is equal to or greater than it's neighbor's height, are never allowed
"""

import collections
import decimal
from typing import List, Tuple

from io_xplane2blender.xplane_helpers import logger
from io_xplane2blender.xplane_props import XPlaneAxisDetentRange
from io_xplane2blender.xplane_types.xplane_bone import XPlaneBone

AxisDetentStruct = collections.namedtuple(
    "AxisDetentStruct", ["start", "end", "height"]
)


def D(v) -> decimal.Decimal:
    """Returns a GUI matching Decimal"""
    return decimal.Decimal(f"{v:.3f}")


def validate_axis_detent_ranges(
    axis_detent_ranges: List[XPlaneAxisDetentRange],
    translation_bone: XPlaneBone,
    v1_min: float,
    v1_max: float,
    heights: Tuple[float, float],
    type_name: str,
) -> bool:
    """heights: the values of dataref 2 at the bottom and top of the lift, which the heights must be between"""
    with decimal.localcontext(decimal.DefaultContext):
        return _validate(
            axis_detent_ranges, translation_bone, v1_min, v1_max, heights, type_name
        )


def _validate(
    axis_detent_ranges, translation_bone, v1_min, v1_max, heights, type_name
) -> bool:
    name = translation_bone.getBlenderName()
    dec_v1_min = D(v1_min)
    dec_v1_max = D(v1_max)
    lowest, highest = (D(min(heights)), D(max(heights)))
    if not len(axis_detent_ranges) > 0:
        logger.error(
            f"Must {name} have axis detent range if manipulator type is {type_name}"
        )
        return False

    if not D(axis_detent_ranges[0].start) == dec_v1_min:
        logger.error(
            f"Axis detent range list for {name} must start at Dataref 1's minimum value {dec_v1_min}"
        )
        return False

    if not D(axis_detent_ranges[-1].end) == dec_v1_max:
        logger.error(
            f"Axis detent range list for {name} must end at Dataref 1's maximum value {dec_v1_max}"
        )
        return False

    if len({D(range_.height) for range_ in axis_detent_ranges}) == 1:
        logger.warn(
            f"All axis detent ranges for {name} have the same height. Check your entered data"
        )

    for i, detent_range in enumerate(axis_detent_ranges):
        start, end, height = (
            D(detent_range.start),
            D(detent_range.end),
            D(detent_range.height),
        )
        if not start <= end:
            logger.error(
                f"The start of axis detent range {detent_range} on {name} must be less than or equal to its end"
            )
            return False

        if not lowest <= height <= highest:
            logger.error(
                f"Height in axis detent range {detent_range} on {name} must be between the values of the lift's"
                f" dataref at the bottom and top of the lift ({lowest} and {highest})"
            )
            return False

        # Pit detection portion
        if len(axis_detent_ranges) == 1 and start == end:
            logger.error(
                f"Axis detent range on {name} cannot have stop pit with only one detent"
            )
            return False

        if i + 1 < len(axis_detent_ranges):
            detent_range_next = axis_detent_ranges[i + 1]
        else:
            detent_range_next = AxisDetentStruct(detent_range.end, v1_max, float("inf"))
        next_start, next_end, next_height = (
            D(detent_range_next.start),
            D(detent_range_next.end),
            D(detent_range_next.height),
        )

        if not end == next_start:
            logger.error(
                f"In {name}'s axis detent range list, the start of a detent range must be the end of the previous"
                f" detent range ({start},{end},{height}), ({next_start},{next_end},{next_height})"
            )
            return False

        if i > 0:
            detent_range_prev = axis_detent_ranges[i - 1]
        else:
            detent_range_prev = AxisDetentStruct(
                v1_min, detent_range.start, float("inf")
            )
        prev_start, prev_end, prev_height = (
            D(detent_range_prev.start),
            D(detent_range_prev.end),
            D(detent_range_prev.height),
        )
        # The spec: "do not create zero length detents that are higher than their neighbors". Level with one is
        # allowed (Laminar's Citation throttles have one)
        if start == end and (height > prev_height or height > next_height):
            logger.error(
                "Stop pit created by {}'s detent range {} must not be higher than"
                " previous {} or next detent ranges {}".format(
                    name,
                    (start, end, height),
                    (prev_start, prev_end, height),
                    (next_start, next_end, next_height),
                )
            )
            return False

    return True
