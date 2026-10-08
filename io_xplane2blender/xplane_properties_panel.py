"""
What every X-Plane panel of the Properties editor shares: it draws like Blender's own panels, the name of a setting to
the left and its value to the right, and rows of buttons or of several settings keep their names inside them.
"""

import functools


def _property_split(draw):
    @functools.wraps(draw)
    def split(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False
        draw(self, context)

    return split


class Properties:
    """The base of a panel in the Properties editor, whose draw() is given the split layout"""

    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "draw" in cls.__dict__:
            cls.draw = _property_split(cls.__dict__["draw"])


def compact_row(layout, align: bool = True):
    """A row of settings that carry their own names (buttons, or several settings side by side), so there is no
    column of names to the left of them"""
    row = layout.row(align=align)
    row.use_property_split = False
    return row


def compact_grid(layout, **kwargs):
    """A grid of buttons, with their names inside them"""
    grid = layout.grid_flow(**kwargs)
    grid.use_property_split = False
    return grid
