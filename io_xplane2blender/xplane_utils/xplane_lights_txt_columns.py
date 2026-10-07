"""
The columns of each kind of lights.txt record (overload type), and the light lists that need special handling.
"""

import enum
from typing import Dict, Optional, Union

OVERLOAD_TYPES = {
    "BILLBOARD_HW",
    "BILLBOARD_SW",
    "SPILL_GND",
    "SPILL_GND_REV",
    "SPILL_HW_DIR",
    "SPILL_HW_FLA",
    "SPILL_SW",
}

SIZE_AS_INTENSITY = {
    "airplane_landing_bb",
    "airplane_landing_pm",
    "airplane_taxi_bb",
    "airplane_taxi_pm",
    "airplane_spot_bb",
    "airplane_spot_pm",
    "airplane_generic_bb",
    "airplane_generic_pm",
    "airplane_nav_bb",
    "airplane_nav_pm",
    "airplane_strobe_bb",
    "airplane_strobe_pm",
    "airplane_beacon_bb",
    "airplane_beacon_pm",
}

BILLBOARD_USES_SPILL_DXYZ = {
    "airplane_landing_bb",
    "airplane_taxi_bb",
    "airplane_spot_bb",
    "airplane_generic_bb",
    "airplane_nav_bb",
    "airplane_strobe_bb",
    "airplane_beacon_bb",
    "spot_params_bb_pm",
    "spot_params_bb_day_pm",
}

BAD_LIGHTS = {"flood_merc_XYZTSB", "flood_LPS_XYZTSB"}


class ColumnName(enum.Enum):
    """ColumnName are labels for the OVERLOAD_TYPE's columns.

    Columns in the lights.txt file are named differently for
    each OVERLOAD_TYPE. In BILLBOARD_HW, the 1st column is 'R'.
    In SPILL_GND it is 'SIZE'. It is easier to understand the
    use of a light overload by talking about labels instead
    of column numbers.

    These are the standard names, as well as a function to handle
    special cases.
    """

    R = "R"
    G = "G"
    B = "B"
    A = "A"
    SIZE = "SIZE"
    CELL_SIZE = "CELL_SIZE"
    CELL_ROW = "CELL_ROW"
    CELL_COL = "CELL_COL"
    DX = "DX"
    DY = "DY"
    DZ = "DZ"
    WIDTH = "WIDTH"
    FREQ = "FREQ"
    PHASE = "PHASE"
    AMP = "AMP"
    DAY = "DAY"
    DREF = "DREF"

    @classmethod
    def param_to_canonical_column_name(
        cls,
        light_name: Optional[str],
        param_name: Union["ColumnName", str],
        overload_type: Optional[str] = None,
    ) -> "ColumnName":
        """Returns the canonical ColumnName based on
        light_name, param_name (probably from a ParsedLight's light_param_def, or
        an unreplaced argument)

        light_name can be empty to only test param_name

        overload_type must be one of OVERLOAD_TYPES or None

        Throws ValueError if no translation could be found"""
        assert overload_type is None or overload_type in OVERLOAD_TYPES
        try:
            if isinstance(param_name, ColumnName):
                return param_name
            else:
                return cls[param_name]
        except KeyError:
            if param_name == "INDEX":
                column_name = cls.A
            elif param_name == "INTENSITY" and light_name in SIZE_AS_INTENSITY:
                column_name = cls.SIZE
            elif (
                param_name == "LEGACY_SIZE"
                and light_name in {"flood_merc_XYZTSB", "flood_LPS_XYZTSB"}
                and overload_type == "BILLBOARD_HW"
            ):
                column_name = cls.SIZE
            elif param_name == "DIR_MAG" and light_name in {"airplane_nav_tail_size"}:
                column_name = cls.B
            elif param_name == "DIR_MAG" and light_name in {
                "airplane_nav_left_size",
                "airplane_nav_right_size",
            }:
                column_name = cls.R
            else:  # including "UNUSED"
                raise ValueError(f"{param_name} has no canonical column name")
            return column_name


# Each overload type's columns, in order. Those starting with "-" can't be parameterized.
# fmt: off
_COLUMNS = {
    "BILLBOARD_HW":  "R G B -A SIZE -CELL_SIZE -CELL_ROW -CELL_COL DX DY DZ WIDTH FREQ PHASE -AMP -DAY",
    "BILLBOARD_SW":  "R G B A SIZE -CELL_SIZE -CELL_ROW -CELL_COL DX DY DZ WIDTH -DREF",
    "SPILL_GND":     "SIZE -CELL_SIZE -CELL_ROW -CELL_COL",
    "SPILL_GND_REV": "SIZE -CELL_SIZE -CELL_ROW -CELL_COL",
    "SPILL_HW_DIR":  "R G B A SIZE DX DY DZ WIDTH -DAY",
    "SPILL_HW_FLA":  "R G B A SIZE FREQ PHASE -AMP -DAY",
    "SPILL_SW":      "R G B A SIZE DX DY DZ WIDTH -DREF",
}
# fmt: on


def get_overload_column_info(overload_type: str) -> Dict[ColumnName, bool]:
    """
    They keys of the returned Dict[ColumnName, IsParameterizable]
    match the overload_type's column order.
    """
    assert overload_type in OVERLOAD_TYPES

    # Raises KeyError if overload_type isn't found.
    return {
        ColumnName[column.lstrip("-")]: not column.startswith("-")
        for column in _COLUMNS[overload_type].split()
    }
