"""
A stand-in for bpy.types.UILayout, so panel and menu draw code can run in background tests. It fails like Blender
would on a wrong property name, enum value, operator, operator setting, menu, list or icon, and records what was drawn.
"""

from types import SimpleNamespace
from typing import List, Tuple

import bpy

_ICONS = None


def _icons():
    global _ICONS
    if _ICONS is None:
        _ICONS = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())
    return _ICONS


def _check_icon(icon: str) -> None:
    assert icon in _icons(), f"unknown icon {icon}"


class FakeOperatorSettings:
    def __init__(self, idname: str, rna):
        object.__setattr__(self, "_idname", idname)
        object.__setattr__(self, "_rna", rna)

    def __setattr__(self, key, value):
        assert key in self._rna.properties, f"{self._idname} has no setting {key}"
        object.__setattr__(self, key, value)


class FakeLayout:
    def __init__(self, drawn: List[Tuple[str, str]] = None):
        object.__setattr__(self, "drawn", drawn if drawn is not None else [])

    def _child(self, *args, **kwargs) -> "FakeLayout":
        return FakeLayout(self.drawn)

    row = column = box = split = grid_flow = column_flow = _child

    def __setattr__(self, key, value):
        assert key in {
            "active",
            "enabled",
            "alert",
            "scale_x",
            "scale_y",
            "alignment",
            "use_property_split",
            "use_property_decorate",
            "operator_context",
            "emboss",
        }, f"layouts have no attribute {key}"
        object.__setattr__(self, key, value)

    def label(self, text: str = "", icon: str = "NONE", **kwargs) -> None:
        _check_icon(icon)
        self.drawn.append(("label", text))

    def separator(self, **kwargs) -> None:
        pass

    def prop(self, data, prop: str, text: str = None, icon: str = "NONE", index: int = -1, **kwargs) -> None:
        assert data is not None, f"prop {prop} of None"
        _check_icon(icon)
        assert prop in data.bl_rna.properties, f"{data.bl_rna.identifier} has no property {prop!r}"
        self.drawn.append(("prop", prop))

    def prop_enum(self, data, prop: str, value: str, text: str = None, icon: str = "NONE", **kwargs) -> None:
        _check_icon(icon)
        assert prop in data.bl_rna.properties, f"{data.bl_rna.identifier} has no property {prop!r}"
        items = data.bl_rna.properties[prop].enum_items.keys()
        # Enums with an items function list nothing here
        assert not items or value in items, f"{prop} has no value {value!r}"
        self.drawn.append(("prop_enum", f"{prop}={value}"))

    def operator(self, idname: str, text: str = None, icon: str = "NONE", **kwargs):
        _check_icon(icon)
        module, _, name = idname.partition(".")
        try:
            rna = getattr(getattr(bpy.ops, module), name).get_rna_type()
        except (AttributeError, KeyError):
            raise AssertionError(f"unknown operator {idname}")
        self.drawn.append(("operator", idname))
        return FakeOperatorSettings(idname, rna)

    def menu(self, menu: str, text: str = None, icon: str = "NONE", **kwargs) -> None:
        _check_icon(icon)
        assert hasattr(bpy.types, menu), f"unknown menu {menu}"
        self.drawn.append(("menu", menu))

    def template_list(self, list_type, list_id, data, prop, active_data, active_prop, **kwargs) -> None:
        assert hasattr(bpy.types, list_type), f"unknown list {list_type}"
        assert hasattr(data, prop), f"no list {prop}"
        assert active_prop in active_data.bl_rna.properties, f"no index {active_prop}"
        self.drawn.append(("list", list_type))

    def template_ID(self, data, prop: str, **kwargs) -> None:
        assert prop in data.bl_rna.properties, f"no property {prop}"
        self.drawn.append(("template_ID", prop))

    def props(self) -> List[str]:
        return [what for kind, what in self.drawn if kind == "prop"]

    def labels(self) -> List[str]:
        return [what for kind, what in self.drawn if kind == "label"]

    def operators(self) -> List[str]:
        return [what for kind, what in self.drawn if kind == "operator"]


def draw_panel(panel_class, context=None, header: bool = True) -> FakeLayout:
    """Runs a panel's draw functions the way Blender does, if its poll lets it show. Returns the layout"""
    context = context or bpy.context
    layout = FakeLayout()
    fake = SimpleNamespace(layout=layout)
    # Blender only draws a sub-panel when its parents show
    shown = panel_class
    while shown is not None:
        if hasattr(shown, "poll") and not shown.poll(context):
            return None
        parent = getattr(shown, "bl_parent_id", "")
        shown = getattr(bpy.types, parent) if parent else None
    if header:
        for method in ("draw_header", "draw_header_preset"):
            if hasattr(panel_class, method):
                getattr(panel_class, method)(fake, context)
    panel_class.draw(fake, context)
    return layout
