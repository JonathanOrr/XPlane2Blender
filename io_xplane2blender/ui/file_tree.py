"""
The Scene tab's list of OBJ files, grouped by the folders they are exported to, like a file browser. A folder opens and
closes, ticks or unticks every file in it, and can be renamed for all of them at once.
"""

from dataclasses import dataclass, field
from typing import Dict, List

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_helpers
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender.xplane_props.file_path import clean_folder, join, split

from .ops_file import XPLANE_OT_select_file_objects, XPLANE_OT_toggle_file_type
from .state import active_file, state


@dataclass
class Folder:
    path: str = ""
    folders: Dict[str, "Folder"] = field(default_factory=dict)
    files: List[bpy.types.Collection] = field(default_factory=list)

    def all_files(self) -> List[bpy.types.Collection]:
        return self.files + [f for sub in self.folders.values() for f in sub.all_files()]


def listed(context) -> List[bpy.types.Collection]:
    """The collections the list shows: files and collections with export settings, or every one with All Collections"""
    in_scene = set(c.name for c in xplane_helpers.get_collections_in_scene(context.scene)[1:])
    panel = state(context)
    needle = panel.file_filter.lower()
    found = []
    for c in bpy.data.collections:
        # Collections with export settings, such as imported OBJs, are listed unticked: one click exports them
        set_up = c.xplane.is_exportable_collection or bool(c.xplane.layer.name.strip())
        if c.name not in in_scene or not (panel.show_all_collections or set_up):
            continue
        if needle and needle not in c.name.lower() and needle not in c.xplane.layer.name.lower():
            continue
        found.append(c)
    return found


def build(collections: List[bpy.types.Collection]) -> Folder:
    root = Folder()
    for collection in sorted(collections, key=lambda c: I.file_name(c).lower()):
        node = root
        folder = split(collection.xplane.layer.name)[0]
        for part in folder.split("/") if folder else []:
            path = join(node.path, part)
            node = node.folders.setdefault(part, Folder(path))
        node.files.append(collection)
    return root


def _open_folders(context) -> set:
    return set(filter(None, state(context).open_folders.split("\n")))


def draw(layout, context) -> None:
    panel = state(context)
    row = layout.row(align=True)
    row.prop(panel, "file_filter", text="", icon="VIEWZOOM")
    row.prop(panel, "show_all_collections", text="", icon="OUTLINER_COLLECTION")
    root = build(listed(context))
    col = layout.box().column(align=True)
    if not root.files and not root.folders:
        col.label(text="No files yet: tick a collection, or use New File From Selection")
        return
    opened = _open_folders(context) if not panel.file_filter else None
    _draw_folder(col, context, root, 0, opened, active_file(context))


def _sides(col, depth: int):
    """A row's left part, flush left and indented by depth, and its right part, flush right"""
    row = col.row(align=True)
    left = row.row(align=True)
    left.alignment = "LEFT"
    for _ in range(depth):
        left.label(text="", icon="BLANK1")
    right = row.row(align=True)
    right.alignment = "RIGHT"
    return left, right


def _draw_folder(col, context, folder: Folder, depth: int, opened, active) -> None:
    for name, sub in sorted(folder.folders.items(), key=lambda item: item[0].lower()):
        is_open = opened is None or sub.path in opened
        files = sub.all_files()
        ticked = sum(f.xplane.is_exportable_collection for f in files)
        left, right = _sides(col, depth)
        icon = "DISCLOSURE_TRI_DOWN" if is_open else "DISCLOSURE_TRI_RIGHT"
        left.operator(XPLANE_OT_open_folder.bl_idname, text=f"{name}/", icon=icon, emboss=False).folder = sub.path
        right.label(text=f"{ticked} of {len(files)} ticked")
        tick = right.operator(
            XPLANE_OT_tick_folder.bl_idname, text="", icon="CHECKBOX_HLT" if ticked else "CHECKBOX_DEHLT", emboss=False
        )
        tick.folder, tick.tick = sub.path, ticked < len(files)
        right.operator(XPLANE_OT_rename_folder.bl_idname, text="", icon="GREASEPENCIL", emboss=False).folder = sub.path
        if is_open:
            _draw_folder(col, context, sub, depth + 1, opened, active)
    for collection in folder.files:
        _draw_file(col, collection, depth, collection == active)


def _draw_file(col, collection: bpy.types.Collection, depth: int, active: bool) -> None:
    left, right = _sides(col, depth)
    left.prop(collection.xplane, "is_exportable_collection", text="", icon="EXPORT", emboss=False)
    ticked = collection.xplane.is_exportable_collection
    left.active = right.active = ticked
    stem = split(collection.xplane.layer.name)[1] or collection.name
    left.operator(XPLANE_OT_choose_file.bl_idname, text=f"{stem}.obj", emboss=active, depress=active).collection = (
        collection.name
    )
    if ticked:
        cockpit = collection.xplane.layer.export_type == C.EXPORT_TYPE_COCKPIT
        right.operator(
            XPLANE_OT_toggle_file_type.bl_idname, text="Cockpit" if cockpit else "Part", emboss=False
        ).collection = collection.name
        right.operator(
            XPLANE_OT_select_file_objects.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False
        ).collection = collection.name


def _in_folder(context, folder: str) -> List[bpy.types.Collection]:
    return [c for c in listed(context) if (split(c.xplane.layer.name)[0] + "/").startswith(folder + "/")]


class XPLANE_OT_choose_file(bpy.types.Operator):
    """Show this file's settings below the list"""

    bl_idname = "xplane.choose_file"
    bl_label = "Choose File"
    bl_options = {"INTERNAL"}

    collection: bpy.props.StringProperty()

    def execute(self, context):
        state(context).file_index = bpy.data.collections.find(self.collection)
        return {"FINISHED"}


class XPLANE_OT_open_folder(bpy.types.Operator):
    """Open or close this folder"""

    bl_idname = "xplane.open_folder"
    bl_label = "Open Folder"
    bl_options = {"INTERNAL"}

    folder: bpy.props.StringProperty()

    def execute(self, context):
        opened = _open_folders(context)
        opened ^= {self.folder}
        state(context).open_folders = "\n".join(sorted(opened))
        return {"FINISHED"}


class XPLANE_OT_tick_folder(bpy.types.Operator):
    """Tick or untick every file in this folder, so Export writes them or leaves them out"""

    bl_idname = "xplane.tick_folder"
    bl_label = "Tick Folder"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    folder: bpy.props.StringProperty()
    tick: bpy.props.BoolProperty()

    def execute(self, context):
        for collection in _in_folder(context, self.folder):
            collection.xplane.is_exportable_collection = self.tick
        return {"FINISHED"}


class XPLANE_OT_rename_folder(bpy.types.Operator):
    """Rename or move this folder: every file in it is exported to the new folder"""

    bl_idname = "xplane.rename_folder"
    bl_label = "Rename Folder"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    folder: bpy.props.StringProperty(options={"HIDDEN"})
    new_folder: bpy.props.StringProperty(name="Folder", description="The new folder, such as objects/cockpit")

    def invoke(self, context, event):
        self.new_folder = self.folder
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        new = clean_folder(self.new_folder)
        files = _in_folder(context, self.folder)
        for collection in files:
            layer = collection.xplane.layer
            folder, stem = split(layer.name)
            layer.name = join(new + folder[len(self.folder) :] if new else folder[len(self.folder) :].lstrip("/"), stem)
        opened = _open_folders(context)
        if self.folder in opened:
            state(context).open_folders = "\n".join(sorted((opened - {self.folder}) | {new}))
        self.report({"INFO"}, f"{len(files)} file(s) now go to {new or 'the .blend file folder'}")
        return {"FINISHED"}


classes = (XPLANE_OT_choose_file, XPLANE_OT_open_folder, XPLANE_OT_tick_folder, XPLANE_OT_rename_folder)
