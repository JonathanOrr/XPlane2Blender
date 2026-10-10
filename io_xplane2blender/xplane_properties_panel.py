"""
What every X-Plane panel of the Properties editor shares: it draws like Blender's own panels. Every line has its name
in the left column and its value in the right one: a setting, a checkbox (named by a heading, like Blender's "Show
In"), a checkbox with the value it turns on, or a row of buttons. Only buttons that do something, help text, lists,
the entries of a list, and dataref and command fields (named above them, as they are long) are as wide as the panel.
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


# Where Blender's own split puts the right column
SPLIT = 0.4


def named(layout, text: str, align: bool = True):
    """A row of buttons or menus in the right column, with text in the left column like the name of a setting"""
    split = layout.split(factor=SPLIT, align=align)
    name = split.row()
    name.alignment = "RIGHT"
    name.label(text=text)
    row = split.row(align=align)
    row.use_property_split = False
    return row


def switched(layout, data, switch: str, value: str, text: str):
    """A value with the checkbox that turns it on in front of it, named text in the left column"""
    row = layout.row(heading=text, align=True)
    row.prop(data, switch, text="")
    sub = row.row(align=True)
    sub.active = getattr(data, switch)
    sub.prop(data, value, text="")
    return row


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
