"""
What every X-Plane panel of the Properties editor shares: everything starts at the left edge, with no column of names.
A checkbox has its name after it, a number has its name inside its field, a checkbox that turns a value on sits in
front of that value, and a row of choice buttons has its name before it. Only text, file and menu fields have a name
to their left, as Blender draws them.
"""

import functools


def _flush_left(draw):
    @functools.wraps(draw)
    def flush(self, context):
        self.layout.use_property_split = False
        self.layout.use_property_decorate = False
        draw(self, context)

    return flush


class Properties:
    """The base of a panel in the Properties editor, whose draw() is given the flush left layout"""

    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if "draw" in cls.__dict__:
            cls.draw = _flush_left(cls.__dict__["draw"])


# Where Blender starts a text, file or menu field after its name, less the gap a split leaves
NAME_WIDTH = 0.235


def named(layout, text: str, align: bool = True):
    """A row of buttons with text before them, where Blender puts the name of a text or menu field"""
    split = layout.split(factor=NAME_WIDTH, align=align)
    # Blender writes a field's name with a colon
    split.label(text=f"{text}:")
    return split.row(align=align)


def switched(layout, data, switch: str, value: str, text: str):
    """A value with the checkbox that turns it on in front of it, its name inside its field"""
    row = layout.row(align=True)
    row.prop(data, switch, text="")
    sub = row.row(align=True)
    sub.active = getattr(data, switch)
    sub.prop(data, value, text=text)
    return row


def compact_row(layout, align: bool = True):
    """A row of settings side by side"""
    return layout.row(align=align)


def compact_grid(layout, **kwargs):
    """A grid of buttons"""
    return layout.grid_flow(**kwargs)
