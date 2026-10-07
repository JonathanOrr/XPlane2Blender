"""
Searching X-Plane's datarefs and commands, together with the ones this .blend already uses.
"""

import os
from typing import Dict, List, Tuple

import bpy

from io_xplane2blender import xplane_helpers
from io_xplane2blender.xplane_utils import xplane_commands_txt_parser, xplane_datarefs_txt_parser

from .state import resolve

_xplane_lists: Dict[str, List[Tuple[str, str]]] = {}
_search_items: List[Tuple[str, str, str]] = []
_search_values: List[str] = []


def _xplane_list(kind: str) -> List[Tuple[str, str]]:
    if kind not in _xplane_lists:
        folder = xplane_helpers.get_plugin_resources_folder()
        if kind == "command":
            content = xplane_commands_txt_parser.get_commands_txt_file_content(
                os.path.join(folder, "Commands.txt").replace(os.sep, "/")
            )
            found = [] if isinstance(content, str) else [(c.command, c.description or "") for c in content]
        else:
            content = xplane_datarefs_txt_parser.get_datarefs_txt_file_content(
                os.path.join(folder, "DataRefs.txt").replace(os.sep, "/")
            )
            found = (
                []
                if isinstance(content, str)
                else [(d.path, " ".join(filter(None, (d.type, d.units, d.description)))) for d in content]
            )
        _xplane_lists[kind] = found
    return _xplane_lists[kind]


def _dataref_paths(datarefs, kind: str):
    for d in datarefs:
        path = d.path.strip()
        if path.startswith("CMND="):
            if kind == "command":
                yield path[5:]
        elif kind == "dataref":
            yield path


def names_in_file(kind: str) -> List[str]:
    """Commands or datarefs this .blend already uses, custom ones included"""
    found = set()
    for obj in bpy.data.objects:
        x = obj.xplane
        found.update(_dataref_paths(x.datarefs, kind))
        if x.manip.enabled:
            fields = ("command", "positive_command", "negative_command") if kind == "command" else ("dataref1", "dataref2")
            found.update(getattr(x.manip, f).strip() for f in fields)
        if kind == "dataref":
            found.add(x.lightLevel_dataref.strip())
    for armature in bpy.data.armatures:
        for bone in armature.bones:
            found.update(_dataref_paths(bone.xplane.datarefs, kind))
    if kind == "dataref":
        found.update(m.xplane.lightLevel_dataref.strip() for m in bpy.data.materials)
        found.update(light.xplane.dataref.strip() for light in bpy.data.lights)
    found.discard("")
    return sorted(found)


def _search_items_callback(self, context):
    return _search_items


class XPLANE_OT_search(bpy.types.Operator):
    """Search X-Plane's own list and the names this file already uses"""

    bl_idname = "xplane.search"
    bl_label = "Search"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_property = "choice"

    kind: bpy.props.EnumProperty(items=(("dataref", "Dataref", ""), ("command", "Command", "")), options={"HIDDEN"})
    target: bpy.props.StringProperty(options={"HIDDEN"})
    choice: bpy.props.EnumProperty(items=_search_items_callback)

    def invoke(self, context, event):
        _search_items.clear()
        _search_values.clear()
        own = names_in_file(self.kind)
        for name in own:
            _search_values.append(name)
            _search_items.append((str(len(_search_values) - 1), f"{name}   (in this file)", "Already used in this file"))
        own_set = set(own)
        for name, description in _xplane_list(self.kind):
            if name in own_set:
                continue
            _search_values.append(name)
            short = description if len(description) < 70 else description[:67] + "..."
            _search_items.append((str(len(_search_values) - 1), f"{name}   {short}", description))
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        owner, attr = resolve(context, self.target)
        if owner is None or not self.choice:
            return {"CANCELLED"}
        value = _search_values[int(self.choice)]
        current = getattr(owner, attr)
        if current.startswith("CMND=") and self.kind == "command":
            value = "CMND=" + value
        setattr(owner, attr, value)
        return {"FINISHED"}


def search_button(layout, kind: str, target: str) -> None:
    op = layout.operator(XPLANE_OT_search.bl_idname, text="", icon="VIEWZOOM")
    op.kind = kind
    op.target = target


def text_with_search(layout, data, prop: str, label: str, kind: str, target: str) -> None:
    """A dataref or command field with its search button. The label goes above it, so long labels are not cut off"""
    col = layout.column(align=True)
    col.label(text=label)
    row = col.row(align=True)
    row.prop(data, prop, text="")
    search_button(row, kind, target)


classes = (XPLANE_OT_search,)
