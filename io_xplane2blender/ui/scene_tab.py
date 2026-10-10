"""
Scene tab: the OBJ files with one Export button, the export options, Unfinished Work and Tools.
Collection tab: whether a collection is an OBJ file.
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_helpers
from io_xplane2blender import xplane_inspector as I
from io_xplane2blender import xplane_light_tools
from io_xplane2blender.viewport.settings import view_settings

from .common import Properties, compact_row, named, wrapped
from .ops_file import (
    XPLANE_OT_check,
    XPLANE_OT_new_file,
    XPLANE_OT_select_file_objects,
    XPLANE_OT_show_file,
    XPLANE_OT_toggle_file_type,
)
from .ops_object import XPLANE_OT_select_object
from .state import state


class XPLANE_UL_files(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        collection = item
        row = layout.row(align=True)
        row.prop(collection.xplane, "is_exportable_collection", text="", icon="EXPORT", emboss=False)
        sub = row.row(align=True)
        sub.active = collection.xplane.is_exportable_collection
        sub.label(text=I.file_name(collection))
        if collection.xplane.is_exportable_collection:
            cockpit = collection.xplane.layer.export_type == C.EXPORT_TYPE_COCKPIT
            sub.operator(
                XPLANE_OT_toggle_file_type.bl_idname, text="Cockpit" if cockpit else "Part", emboss=False
            ).collection = collection.name
            sub.operator(
                XPLANE_OT_select_file_objects.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False
            ).collection = collection.name

    def draw_filter(self, context, layout):
        layout.prop(state(context), "show_all_collections")
        layout.prop(self, "filter_name", text="")

    def filter_items(self, context, data, propname):
        in_scene = set(c.name for c in xplane_helpers.get_collections_in_scene(context.scene)[1:])
        show_all = state(context).show_all_collections
        needle = self.filter_name.lower()
        flags = []
        for c in getattr(data, propname):
            # Collections with export settings, such as imported OBJs, are listed unticked: one click exports them
            set_up = c.xplane.is_exportable_collection or bool(c.xplane.layer.name.strip())
            shown = c.name in in_scene and (show_all or set_up)
            if shown and needle:
                shown = needle in c.name.lower() or needle in c.xplane.layer.name.lower()
            flags.append(self.bitflag_filter_item if shown else 0)
        return flags, []


class _SceneTab(Properties):
    bl_context = "scene"


class XPLANE_PT_export(_SceneTab, bpy.types.Panel):
    bl_label = "X-Plane Export"

    def draw(self, context):
        layout = self.layout
        files = I.export_files(context.scene)
        rows = max(2, min(len(files), 8))
        layout.template_list("XPLANE_UL_files", "", bpy.data, "collections", state(context), "file_index", rows=rows)
        for root in (f for f in files if isinstance(f, bpy.types.Object)):
            op = layout.operator(XPLANE_OT_show_file.bl_idname, text=f"{I.file_name(root)} (root object)", icon="OBJECT_DATA")
            op.root_object = root.name
        layout.operator(XPLANE_OT_new_file.bl_idname, text="New File From Selection", icon="ADD")

        col = layout.column()
        col.scale_y = 1.5
        if not bpy.data.filepath:
            col.enabled = False
            col.operator("scene.export_to_relative_dir", text="Save The .blend First", icon="EXPORT")
            layout.label(text="OBJs are written next to the .blend file", icon="INFO")
            return
        col.enabled = bool(files)
        text = f"Export {len(files)} File{'s' if len(files) != 1 else ''}"
        col.operator("scene.export_to_relative_dir", text=text, icon="EXPORT")
        layout.label(text=f"To {bpy.path.abspath('//')}", icon="FILE_FOLDER")


def _developer_layout(layout, scene) -> None:
    x = scene.xplane
    col = layout.column()
    sub = col.column(heading="Debugging")
    sub.prop(x, "dev_enable_breakpoints")
    sub.prop(x, "dev_export_as_dry_run")
    op = col.operator("scene.export_to_relative_dir", text="Export To Fixtures Folder", icon="EXPORT")
    op.initial_dir = "fixtures"
    col.operator("scene.dev_apply_default_material_to_all")
    col.operator("scene.dev_root_names_from_objects")
    col.operator("scene.dev_create_lights_txt_summary")
    row = col.row(align=True)
    row.prop(x, "dev_fake_xplane2blender_version", text="")
    row.operator("scene.dev_rerun_updater")
    col.label(text="Opened With")
    for entry in reversed(list(x.xplane2blender_ver_history)):
        col.label(text=str(entry), icon="DOT")


class XPLANE_PT_export_options(_SceneTab, bpy.types.Panel):
    bl_label = "Options"
    bl_parent_id = "XPLANE_PT_export"
    bl_order = 9
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        x = context.scene.xplane
        col = self.layout.column(heading="Export")
        col.prop(x, "optimize", text="Smaller Files (share vertices)")
        col.prop(x, "debug", text="Debug Info")
        if x.debug:
            col.prop(x, "log")
        col.column(heading="Developer").prop(x, "plugin_development", text="Tools")
        col.label(text=f"Add-on {xplane_helpers.VerStruct.current()}", icon="INFO")
        if x.plugin_development:
            _developer_layout(col.box(), context.scene)


class XPLANE_UL_check(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        op = row.operator(XPLANE_OT_select_object.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False)
        op.name = item.object_name
        row.label(text=f"{item.object_name}: {item.text}")


class XPLANE_PT_check(_SceneTab, bpy.types.Panel):
    bl_label = "X-Plane Unfinished Work"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = state(context)
        layout.operator(XPLANE_OT_check.bl_idname, text="Check Again" if s.checked else "Check", icon="VIEWZOOM")
        if not s.checked:
            wrapped(
                layout,
                "Lists what is not filled in yet in the export files. Exports never wait for it: what is missing is left out.",
            )
        elif not s.check_items:
            layout.label(text="Nothing unfinished", icon="CHECKMARK")
        else:
            layout.label(text=f"{len(s.check_items)} thing(s) to finish")
            layout.template_list("XPLANE_UL_check", "", s, "check_items", s, "check_index", rows=6)


class XPLANE_PT_tools(_SceneTab, bpy.types.Panel):
    bl_label = "X-Plane Tools"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        view = view_settings(context)
        if view is not None:
            row = compact_row(layout)
            row.prop(view, "show_click_zones", toggle=True, icon="RESTRICT_SELECT_OFF")
            row.prop(view, "click_labels", text="")
        layout.operator(
            xplane_light_tools.XPLANE_OT_lights_preview.bl_idname, text="Preview Every Light As In X-Plane", icon="LIGHT"
        ).selected_only = False
        layout.operator("xplane.tidy_viewport", icon="OUTLINER_OB_EMPTY")
        layout.operator("xplane.workspace", text="Open The X-Plane Workspace", icon="WORKSPACE")


class XPLANE_PT_collection(Properties, bpy.types.Panel):
    bl_label = "X-Plane"
    bl_context = "collection"

    @classmethod
    def poll(cls, context):
        collection = context.collection
        return collection is not None and collection != context.scene.collection

    def draw_header(self, context):
        self.layout.prop(context.collection.xplane, "is_exportable_collection", text="")

    def draw(self, context):
        layout = self.layout
        collection = context.collection
        layer = collection.xplane.layer
        if not collection.xplane.is_exportable_collection:
            wrapped(layout, "Tick to export this collection as an OBJ file.", "INFO")
            if not layer.name.strip():
                return
        col = layout.column()
        col.active = collection.xplane.is_exportable_collection
        col.prop(layer, "name", text="Saved As")
        row = named(col, "Is A")
        row.prop_enum(layer, "export_type", C.EXPORT_TYPE_AIRCRAFT, text="Aircraft Part")
        row.prop_enum(layer, "export_type", C.EXPORT_TYPE_COCKPIT, text="Cockpit")
        op = layout.operator(XPLANE_OT_show_file.bl_idname, text="File Settings And Export", icon="SCENE_DATA")
        op.collection = collection.name


classes = (
    XPLANE_UL_files,
    XPLANE_PT_export,
    XPLANE_PT_export_options,
    XPLANE_UL_check,
    XPLANE_PT_check,
    XPLANE_PT_tools,
    XPLANE_PT_collection,
)
