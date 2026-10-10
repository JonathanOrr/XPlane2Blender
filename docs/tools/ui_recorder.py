"""
Runs a panel's drawing code with a stand-in layout that writes down what it would show: labels, settings with their
names and values, buttons and menus, nested as rows, columns and boxes. Works without a window, so tests can tell when a
panel no longer draws what its screenshot in the docs shows.
"""

import contextlib
import types
from typing import Any, Dict, List, Optional, Tuple

import bpy


def _operator_label(idname: str) -> str:
    module, _, name = idname.partition(".")
    cls = getattr(bpy.types, f"{module.upper()}_OT_{name}", None)
    if cls is not None:
        return getattr(cls, "bl_label", idname)
    try:
        return getattr(bpy.ops, module).__getattr__(name).get_rna_type().name
    except (AttributeError, KeyError):
        return idname


def _operator_tip(idname: str) -> str:
    module, _, name = idname.partition(".")
    cls = getattr(bpy.types, f"{module.upper()}_OT_{name}", None)
    if cls is not None:
        return (getattr(cls, "bl_description", "") or (cls.__doc__ or "")).strip()
    try:
        return getattr(bpy.ops, module).__getattr__(name).get_rna_type().description
    except (AttributeError, KeyError):
        return ""


def _operator_class(idname: str) -> Optional[type]:
    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    return next(
        (
            c
            for c in subclasses(bpy.types.Operator)
            if getattr(c, "bl_idname", "") == idname and "description" in vars(c)
        ),
        None,
    )


def _operator_tip_for(idname: str, values: Dict[str, Any]) -> Optional[str]:
    """The tooltip of a button whose operator words it by the button's properties (its description classmethod)"""
    cls = _operator_class(idname)
    if cls is None:
        return None
    defaults = {
        p.identifier: getattr(p, "default", None)
        for p in getattr(bpy.ops, idname.partition(".")[0])
        .__getattr__(idname.partition(".")[2])
        .get_rna_type()
        .properties
    }
    return cls.description(bpy.context, types.SimpleNamespace(**{**defaults, **values}))


def _menu_label(idname: str) -> str:
    cls = getattr(bpy.types, idname, None)
    return getattr(cls, "bl_label", idname) if cls else idname


def _value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    if isinstance(value, bpy.types.ID):
        return value.name
    if isinstance(value, set):
        return sorted(value)
    try:
        return [_value(v) for v in value]
    except TypeError:
        return type(value).__name__


class _OperatorProperties:
    """What layout.operator() returns: the button's properties, set by the panel after drawing it"""

    def __init__(self, node: Dict[str, Any]):
        object.__setattr__(self, "_node", node)

    def __setattr__(self, name: str, value: Any) -> None:
        self._node.setdefault("set", {})[name] = _value(value)
        tip = _operator_tip_for(self._node["operator"], self._node["set"])
        if tip:
            self._node["_tip"] = tip

    def __getattr__(self, name: str) -> Any:
        return self._node.get("set", {}).get(name)


class Recorder:
    """A stand-in for bpy.types.UILayout"""

    _FLAGS = ("enabled", "active", "alert")

    def __init__(self, kind: str = "layout"):
        object.__setattr__(self, "node", {"kind": kind, "items": []})
        for flag in self._FLAGS:
            object.__setattr__(self, flag, True)
        object.__setattr__(self, "use_property_split", False)
        object.__setattr__(self, "use_property_decorate", True)

    def __setattr__(self, name: str, value: Any) -> None:
        object.__setattr__(self, name, value)
        if name in self._FLAGS and not value:
            self.node[name] = False

    def _add(self, item: Dict[str, Any]) -> Dict[str, Any]:
        self.node["items"].append(item)
        return item

    def _child(self, kind: str) -> "Recorder":
        child = Recorder(kind)
        object.__setattr__(child, "use_property_split", self.use_property_split)
        self._add(child.node)
        return child

    # ---- containers
    def _headed(self, kind: str, heading: str = "") -> "Recorder":
        child = self._child(kind)
        if heading:
            # Blender draws a heading in the left column, as the name of the first checkbox
            child.node["heading"] = heading
            child.label(text=heading)
        return child

    def row(self, heading: str = "", **kwargs) -> "Recorder":
        return self._headed("row", heading)

    def column(self, heading: str = "", **kwargs) -> "Recorder":
        return self._headed("column", heading)

    def box(self) -> "Recorder":
        return self._child("box")

    def split(self, **kwargs) -> "Recorder":
        return self._child("split")

    def grid_flow(self, **kwargs) -> "Recorder":
        return self._child("grid")

    def column_flow(self, **kwargs) -> "Recorder":
        return self._child("columns")

    def menu_pie(self) -> "Recorder":
        return self._child("pie")

    # ---- items
    def label(self, text: str = "", icon: str = "NONE", **kwargs) -> None:
        self._add(
            {
                "kind": "label",
                "text": text,
                **({"icon": icon} if icon != "NONE" else {}),
            }
        )

    def separator(self, **kwargs) -> None:
        pass

    def prop(
        self, data, prop: str, text: Optional[str] = None, icon: str = "NONE", **kwargs
    ) -> None:
        rna = data.bl_rna.properties.get(prop) if hasattr(data, "bl_rna") else None
        name = text if text is not None else (rna.name if rna else prop)
        item = {
            "kind": "prop",
            "prop": prop,
            "text": name,
            "value": _value(getattr(data, prop, None)),
        }
        if rna is not None:
            item["_tip"] = rna.description
            item["_name"] = rna.name
            if rna.type == "ENUM" and not rna.is_enum_flag:
                item["_choices"] = [e.name for e in rna.enum_items]
            if rna.type == "BOOLEAN":
                item["_checkbox"] = True
        if rna is not None and rna.type == "ENUM" and kwargs.get("expand"):
            item["expand"] = True
        self._add(item)

    def prop_enum(
        self, data, prop: str, value: str, text: Optional[str] = None, **kwargs
    ) -> None:
        rna = data.bl_rna.properties[prop]
        name = (
            text
            if text is not None
            else next((e.name for e in rna.enum_items if e.identifier == value), value)
        )
        item = next((e for e in rna.enum_items if e.identifier == value), None)
        self._add(
            {
                "kind": "prop_enum",
                "prop": prop,
                "option": value,
                "text": name,
                "on": getattr(data, prop) == value,
                "_tip": (item.description if item else "") or rna.description,
                "_name": rna.name,
            }
        )

    def prop_search(
        self,
        data,
        prop: str,
        search_data,
        search_prop: str,
        text: Optional[str] = None,
        **kwargs,
    ) -> None:
        self.prop(data, prop, text=text)

    def operator(
        self, idname: str, text: Optional[str] = None, icon: str = "NONE", **kwargs
    ) -> _OperatorProperties:
        item = self._add(
            {
                "kind": "operator",
                "operator": idname,
                "text": text if text is not None else _operator_label(idname),
                "_tip": _operator_tip_for(idname, {}) or _operator_tip(idname),
                "_name": _operator_label(idname),
            }
        )
        return _OperatorProperties(item)

    def operator_menu_enum(
        self, idname: str, prop: str, text: Optional[str] = None, **kwargs
    ) -> _OperatorProperties:
        return self.operator(idname, text=text)

    def menu(self, menu: str, text: Optional[str] = None, **kwargs) -> None:
        cls = getattr(bpy.types, menu, None)
        tip = (
            (getattr(cls, "bl_description", "") or (cls.__doc__ or "")).strip()
            if cls
            else ""
        )
        self._add(
            {
                "kind": "menu",
                "menu": menu,
                "text": text if text is not None else _menu_label(menu),
                "_tip": tip,
                "_name": _menu_label(menu),
            }
        )

    def popover(self, panel: str, text: str = "", **kwargs) -> None:
        self._add({"kind": "popover", "panel": panel, "text": text})

    def template_list(
        self,
        listtype_name: str,
        list_id: str,
        dataptr,
        propname: str,
        active_dataptr,
        active_propname: str,
        **kwargs,
    ) -> None:
        self._add(
            {
                "kind": "list",
                "list": listtype_name,
                "items": len(getattr(dataptr, propname)),
            }
        )

    def context_pointer_set(self, name: str, data) -> None:
        pass


class _Panel:
    """The panel's self: its layout is the recorder, everything else comes from its class"""

    def __init__(self, cls, layout: Recorder):
        self.__dict__.update(layout=layout, _cls=cls)

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._cls, name)
        if isinstance(attr, types.FunctionType):
            return types.MethodType(attr, self)
        return attr


class _Context:
    """bpy.context with some members replaced"""

    def __init__(self, overrides: Dict[str, Any]):
        self.__dict__["_overrides"] = overrides

    def __getattr__(self, name: str) -> Any:
        if name in self._overrides:
            return self._overrides[name]
        return getattr(bpy.context, name)


def without_notes(node: Any) -> Any:
    """The recording without what a picture does not show (tooltips, names behind the labels)"""
    if isinstance(node, dict):
        return {k: without_notes(v) for k, v in node.items() if not k.startswith("_")}
    if isinstance(node, list):
        return [without_notes(v) for v in node]
    return node


@contextlib.contextmanager
def fixed_line_width(width: int = 60):
    """Text the panels wrap to their width is wrapped as wide as this, as it would be in a Properties editor that wide"""
    from io_xplane2blender.ui import common

    old = common._line_width
    common._line_width = lambda icon: width - (6 if icon != "NONE" else 3)
    try:
        yield
    finally:
        common._line_width = old


def _children(cls) -> List[type]:
    idname = getattr(cls, "bl_idname", cls.__name__)
    found = []
    for name in dir(bpy.types):
        sub = getattr(bpy.types, name)
        if (
            isinstance(sub, type)
            and issubclass(sub, bpy.types.Panel)
            and getattr(sub, "bl_parent_id", "") == idname
        ):
            found.append(sub)
    return sorted(found, key=lambda c: getattr(c, "bl_order", 0))


def record_panel(
    cls,
    overrides: Optional[Dict[str, Any]] = None,
    children: bool = True,
    opened: Tuple[str, ...] = (),
    hidden: Tuple[str, ...] = (),
) -> Optional[Dict[str, Any]]:
    """What the panel and its sub-panels draw, or None when it is not shown (its poll is false or it is hidden).
    Sub-panels closed by default are closed unless they are in opened"""
    if getattr(cls, "bl_idname", cls.__name__) in hidden:
        return None
    context = _Context(overrides or {})
    poll = getattr(cls, "poll", None)
    if poll is not None and not poll(context):
        return None
    node: Dict[str, Any] = {
        "kind": "panel",
        "panel": getattr(cls, "bl_idname", cls.__name__),
        "label": cls.bl_label,
    }
    # A sub-panel closed by default shows only its header in a new file, as in the screenshots
    idname = getattr(cls, "bl_idname", cls.__name__)
    closed = (
        bool(getattr(cls, "bl_parent_id", ""))
        and "DEFAULT_CLOSED" in getattr(cls, "bl_options", set())
        and idname not in opened
    )
    if closed:
        node["closed"] = True
    for part in ("draw_header", "draw_header_preset") + (() if closed else ("draw",)):
        if hasattr(cls, part):
            layout = Recorder(part)
            getattr(_Panel(cls, layout), part)(context)
            node[part] = layout.node["items"]
    if children and not closed:
        node["children"] = [
            n
            for n in (
                record_panel(c, overrides, True, opened, hidden) for c in _children(cls)
            )
            if n is not None
        ]
    return node


def record_menu(cls, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What a menu (or pie menu) draws"""
    layout = Recorder("draw")
    cls.draw(_Panel(cls, layout), _Context(overrides or {}))
    return {
        "kind": "menu",
        "menu": getattr(cls, "bl_idname", cls.__name__),
        "label": cls.bl_label,
        "draw": layout.node["items"],
    }


def record_function(draw, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What a draw function an add-on appends to one of Blender's own panels or menus draws"""
    layout = Recorder("draw")
    draw(types.SimpleNamespace(layout=layout, bl_idname=""), _Context(overrides or {}))
    return {
        "kind": "function",
        "function": f"{draw.__module__}.{draw.__name__}",
        "draw": layout.node["items"],
    }


class _Operator(_Panel):
    """An operator's self in its draw(): its settings at their defaults"""

    def __init__(self, cls, layout: Recorder):
        super().__init__(cls, layout)
        module, _, name = cls.bl_idname.partition(".")
        self.__dict__["bl_rna"] = getattr(getattr(bpy.ops, module), name).get_rna_type()

    def __getattr__(self, name: str) -> Any:
        rna = self.bl_rna.properties.get(name)
        if rna is not None and name != "rna_type":
            if getattr(rna, "is_array", False):
                return tuple(rna.default_array)
            if rna.type == "ENUM":
                if not len(rna.enum_items):
                    return ""  # Its choices are made from what is being imported
                return rna.default_flag if rna.is_enum_flag else rna.default
            if rna.type in ("POINTER", "COLLECTION"):
                return None
            return rna.default
        return super().__getattr__(name)


def record_operator(cls, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """What an operator's own draw() shows, such as the options in the side panel of a file browser"""
    layout = Recorder("draw")
    cls.draw(_Operator(cls, layout), _Context(overrides or {}))
    return {
        "kind": "operator_options",
        "operator": cls.bl_idname,
        "label": cls.bl_label,
        "draw": layout.node["items"],
    }
