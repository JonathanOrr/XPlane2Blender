"""
The X-Plane tab of the 3D viewport's sidebar (N): one place for everything, following the selection.

- Selected: what the active object is, which file it exports in, and a card for each thing it can do
  (Clickable, Moves, Shows / Hides, Glow, Light, Surface, Attachment), in plain words
- Export: the OBJ files of the scene, one Export button, and the settings of the chosen file
- Unfinished Work: a list of what is not filled in yet. It never stops an export
- Tools: find and replace, tables

The settings underneath are the same stored X-Plane properties as before, so older .blend files open unchanged.
"""

import os
from types import SimpleNamespace
from typing import Dict, List, Optional, Tuple

import bpy

from io_xplane2blender import (
    xplane_anim_presets,
    xplane_constants as C,
    xplane_helpers,
    xplane_inspector as I,
    xplane_light_tools,
    xplane_ui,
    xplane_xp12,
)
from io_xplane2blender.xplane_ops import removeDatarefFCurve
from io_xplane2blender.xplane_utils import (
    xplane_commands_txt_parser,
    xplane_datarefs_txt_parser,
    xplane_lights_txt_parser,
)

CATEGORY = "X-Plane"
ADDON = __package__


def preferences(context=None) -> Optional[bpy.types.AddonPreferences]:
    addon = (context or bpy.context).preferences.addons.get(ADDON)
    return addon.preferences if addon else None


def classic_panels(context) -> bool:
    prefs = preferences(context)
    return bool(prefs and prefs.classic_panels)


class XPlaneAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON

    classic_panels: bpy.props.BoolProperty(
        name="Classic Panels In The Properties Editor",
        description="Also show the X-Plane panels of earlier versions in the Properties editor's Object, Material, Light and Scene tabs",
        default=False,
    )

    def draw(self, context):
        self.layout.label(text="Everything is in the 3D viewport's sidebar (N), X-Plane tab.")
        self.layout.prop(self, "classic_panels")


# ---- Search: X-Plane's datarefs and commands, and the ones this file already uses -------------------------------
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


def names_in_file(kind: str) -> List[str]:
    """Commands or datarefs this .blend already uses, custom ones included"""
    found = set()
    for obj in bpy.data.objects:
        x = obj.xplane
        for d in x.datarefs:
            path = d.path.strip()
            if path.startswith("CMND="):
                if kind == "command":
                    found.add(path[5:])
            elif kind == "dataref" and path:
                found.add(path)
        if x.manip.enabled:
            fields = ("command", "positive_command", "negative_command") if kind == "command" else ("dataref1", "dataref2")
            found.update(getattr(x.manip, f).strip() for f in fields)
        if kind == "dataref":
            found.add(x.lightLevel_dataref.strip())
    if kind == "dataref":
        found.update(m.xplane.lightLevel_dataref.strip() for m in bpy.data.materials)
        found.update(l.xplane.dataref.strip() for l in bpy.data.lights)
    found.discard("")
    return sorted(found)


def _search_items_callback(self, context):
    return _search_items


def _resolve(context, target: str):
    """'object:xplane.manip.command' -> (the active object's manip settings, 'command')"""
    where, _, path = target.partition(":")
    obj = context.active_object
    base = {
        "object": obj,
        "material": obj.active_material if obj else None,
        "light": obj.data if obj is not None and obj.type == "LIGHT" else None,
        "file": active_file(context),
    }[where]
    if base is None:
        return None, None
    parent, _, attr = path.rpartition(".")
    return (base.path_resolve(parent) if parent else base), attr


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
        owner, attr = _resolve(context, self.target)
        if owner is None or not self.choice:
            return {"CANCELLED"}
        value = _search_values[int(self.choice)]
        current = getattr(owner, attr)
        if current.startswith("CMND=") and self.kind == "command":
            value = "CMND=" + value
        setattr(owner, attr, value)
        return {"FINISHED"}


def text_with_search(layout, data, prop: str, label: str, kind: str, target: str) -> None:
    """A dataref or command field with its search button. The label goes above it: the sidebar is narrow"""
    col = layout.column(align=True)
    col.label(text=label)
    row = col.row(align=True)
    row.prop(data, prop, text="")
    op = row.operator(XPLANE_OT_search.bl_idname, text="", icon="VIEWZOOM")
    op.kind = kind
    op.target = target


# ---- State kept while Blender runs ------------------------------------------------------------------------------
class XPlaneCheckItem(bpy.types.PropertyGroup):
    object_name: bpy.props.StringProperty()
    text: bpy.props.StringProperty()


class XPlaneSidebarState(bpy.types.PropertyGroup):
    file_index: bpy.props.IntProperty(name="File", default=-1)
    show_all_collections: bpy.props.BoolProperty(
        name="All Collections",
        description="List every collection, so any of them can be made an export file",
        default=False,
    )
    show_click_zones: bpy.props.BoolProperty(
        name="Click Zones",
        description="Outline what can be clicked in X-Plane: orange runs commands, blue sets datarefs, green is dragged",
        default=False,
    )
    click_labels: bpy.props.EnumProperty(
        name="Click Labels",
        description="Say what clicking each object does",
        items=(
            ("OFF", "No Labels", "No labels"),
            ("SELECTED", "Labels: Selected", "Label the selected clickable objects"),
            ("ALL", "Labels: All", "Label every clickable object"),
        ),
        default="OFF",
    )
    checked: bpy.props.BoolProperty(default=False)
    check_items: bpy.props.CollectionProperty(type=XPlaneCheckItem)
    check_index: bpy.props.IntProperty()


def state(context) -> XPlaneSidebarState:
    return context.window_manager.xplane_sidebar


def active_file(context) -> Optional[I.FileOwner]:
    """The file the Export panel shows: the one picked in the list, otherwise the active object's"""
    scene = context.scene
    index = state(context).file_index
    if 0 <= index < len(bpy.data.collections):
        collection = bpy.data.collections[index]
        if I.is_file(collection) and collection in xplane_helpers.get_collections_in_scene(scene):
            return collection
    obj = context.active_object
    if obj is not None:
        owners = I.files_of(obj, scene)
        if owners:
            return owners[0]
    files = I.export_files(scene)
    return files[0] if files else None


# ---- Operators -----------------------------------------------------------------------------------------------------
def _selected_or_active(context) -> List[bpy.types.Object]:
    objects = list(context.selected_objects)
    if context.active_object is not None and context.active_object not in objects:
        objects.append(context.active_object)
    return objects


class XPLANE_OT_set_control_kind(bpy.types.Operator):
    """Make the selected objects clickable, as this kind of control"""

    bl_idname = "xplane.set_control_kind"
    bl_label = "Set Kind Of Control"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    kind: bpy.props.StringProperty()

    @classmethod
    def description(cls, context, properties):
        kind = I.CONTROL_KINDS.get(properties.kind)
        return kind.help if kind else ""

    def execute(self, context):
        new = I.CONTROL_KINDS[self.kind]
        meshes = [o for o in _selected_or_active(context) if o.type == "MESH"]
        for obj in meshes:
            manip = obj.xplane.manip
            old_cursor = I.control_kind(manip).cursor
            fresh = not manip.enabled
            manip.enabled = True
            manip.type = self.kind
            if fresh or manip.cursor == old_cursor:
                manip.cursor = new.cursor
        if not meshes:
            self.report({"WARNING"}, "Select the meshes to make clickable")
            return {"CANCELLED"}
        self.report({"INFO"}, f"{len(meshes)} object(s) are now: {new.label}")
        return {"FINISHED"}


class XPLANE_MT_control_kind(bpy.types.Menu):
    bl_idname = "XPLANE_MT_control_kind"
    bl_label = "Kind Of Control"

    def draw(self, context):
        row = self.layout.row()
        for group in I.GROUPS:
            col = row.column()
            col.label(text=group)
            for manip_type, kind in I.CONTROL_KINDS.items():
                if kind.group == group:
                    col.operator(XPLANE_OT_set_control_kind.bl_idname, text=kind.label).kind = manip_type


class XPLANE_OT_copy_to_selected(bpy.types.Operator):
    """Copy these X-Plane settings from the active object to the other selected objects"""

    bl_idname = "xplane.copy_to_selected"
    bl_label = "Copy To Selected"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    what: bpy.props.EnumProperty(
        items=(
            ("CLICK", "Clickable", ""),
            ("GLOW", "Glow", ""),
            ("VISIBILITY", "Shows / Hides", ""),
            ("LIGHT", "Light", ""),
            ("ATTACHMENT", "Attachment", ""),
        )
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and len(context.selected_objects) > 1

    def execute(self, context):
        source = context.active_object
        done = sum(
            1
            for target in context.selected_objects
            if target != source and I.copy_settings(self.what, source, target)
        )
        self.report({"INFO"}, f"Copied to {done} object(s)")
        return {"FINISHED"}


def copy_button(layout, context, what: str) -> None:
    if len(context.selected_objects) > 1:
        layout.operator(XPLANE_OT_copy_to_selected.bl_idname, text="", icon="DUPLICATE", emboss=False).what = what


class XPLANE_OT_add_dataref(bpy.types.Operator):
    """Add a dataref to the active object"""

    bl_idname = "xplane.add_dataref"
    bl_label = "Add Dataref"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    anim_type: bpy.props.EnumProperty(
        items=(
            (C.ANIM_TYPE_TRANSFORM, "Moves", "Keyframe the object's movement against the dataref"),
            (C.ANIM_TYPE_SHOW, "Show When", "Show the object while the dataref is in a range"),
            (C.ANIM_TYPE_HIDE, "Hide When", "Hide the object while the dataref is in a range"),
        )
    )

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        dataref = context.active_object.xplane.datarefs.add()
        dataref.anim_type = self.anim_type
        if self.anim_type != C.ANIM_TYPE_TRANSFORM:
            dataref.show_hide_v1, dataref.show_hide_v2 = 1.0, 1.0
        return {"FINISHED"}


class XPLANE_OT_remove_dataref(bpy.types.Operator):
    """Remove this dataref and its keyframes from the active object"""

    bl_idname = "xplane.remove_dataref"
    bl_label = "Remove Dataref"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.active_object
        if obj is None or not 0 <= self.index < len(obj.xplane.datarefs):
            return {"CANCELLED"}
        obj.xplane.datarefs.remove(self.index)
        # The keys of the datarefs after this one move down with them
        removeDatarefFCurve(obj, self.index)
        return {"FINISHED"}


class XPLANE_OT_key_pose(bpy.types.Operator):
    """Key where the object is now at this dataref value: pose it, type the value, click. Keys are linear, like X-Plane"""

    bl_idname = "xplane.key_pose"
    bl_label = "Key This Pose"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: bpy.props.IntProperty()

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        frame = context.scene.frame_current
        obj.keyframe_insert(data_path=f"xplane.datarefs[{self.index}].value", frame=frame, group="XPlane Datarefs")
        obj.keyframe_insert(data_path="location", frame=frame, group="Object Transforms")
        rotation = {
            "QUATERNION": "rotation_quaternion",
            "AXIS_ANGLE": "rotation_axis_angle",
        }.get(obj.rotation_mode, "rotation_euler")
        obj.keyframe_insert(data_path=rotation, frame=frame, group="Object Transforms")
        for fcurve in xplane_helpers.get_action_fcurves(obj):
            if fcurve.data_path in ("location", rotation) or fcurve.data_path.startswith("xplane.datarefs"):
                for key in fcurve.keyframe_points:
                    if key.co[0] == frame:
                        key.interpolation = "LINEAR"
        return {"FINISHED"}


class XPLANE_OT_go_to_frame(bpy.types.Operator):
    """Go to this key to see or change the pose"""

    bl_idname = "xplane.go_to_frame"
    bl_label = "Go To Key"
    bl_options = {"INTERNAL"}

    frame: bpy.props.FloatProperty()

    def execute(self, context):
        context.scene.frame_set(int(round(self.frame)))
        return {"FINISHED"}


class XPLANE_OT_new_file(bpy.types.Operator):
    """Make a new OBJ file holding the selected objects (and their children). They leave the files they were in"""

    bl_idname = "xplane.new_file"
    bl_label = "New File From Selection"
    bl_options = {"REGISTER", "UNDO"}

    name: bpy.props.StringProperty(name="File Name", description="The OBJ's name, also a path below the .blend's folder")
    file_type: bpy.props.EnumProperty(
        name="Kind",
        items=(
            ("AUTO", "Automatic", "Cockpit when something is clickable, otherwise aircraft part"),
            (C.EXPORT_TYPE_AIRCRAFT, "Aircraft Part", "Seen from outside and inside, nothing clickable"),
            (C.EXPORT_TYPE_COCKPIT, "Cockpit", "The cockpit OBJ: clickable things, panel textures, camera collision"),
        ),
        default="AUTO",
    )

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def invoke(self, context, event):
        if not self.name:
            self.name = context.active_object.name if context.active_object else "new_object"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        cockpit = None if self.file_type == "AUTO" else self.file_type == C.EXPORT_TYPE_COCKPIT
        collection = I.move_into_new_file(context.selected_objects, self.name.strip() or "new_object", context.scene, cockpit)
        state(context).file_index = bpy.data.collections.find(collection.name)
        self.report({"INFO"}, f"New file {I.file_name(collection)} with {len(collection.all_objects)} object(s)")
        return {"FINISHED"}


class XPLANE_OT_move_to_file(bpy.types.Operator):
    """Move the selected objects (and their children) into this file"""

    bl_idname = "xplane.move_to_file"
    bl_label = "Move To File"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    collection: bpy.props.StringProperty()

    def execute(self, context):
        target = bpy.data.collections.get(self.collection)
        if target is None:
            return {"CANCELLED"}
        moving = []
        for obj in context.selected_objects:
            for o in (obj, *obj.children_recursive):
                if o not in moving:
                    moving.append(o)
        inside = [c for owner in I.export_files(context.scene) if isinstance(owner, bpy.types.Collection)
                  for c in (owner, *owner.children_recursive)]
        for obj in moving:
            for old in inside:
                if old != target and obj.name in old.objects:
                    old.objects.unlink(obj)
            if obj.name not in target.objects:
                target.objects.link(obj)
            if obj.name in context.scene.collection.objects:
                context.scene.collection.objects.unlink(obj)
        self.report({"INFO"}, f"Moved {len(moving)} object(s) into {I.file_name(target)}")
        return {"FINISHED"}


class XPLANE_MT_move_to_file(bpy.types.Menu):
    bl_idname = "XPLANE_MT_move_to_file"
    bl_label = "Move To File"

    def draw(self, context):
        files = [f for f in I.export_files(context.scene) if isinstance(f, bpy.types.Collection)]
        for owner in files:
            self.layout.operator(XPLANE_OT_move_to_file.bl_idname, text=I.file_name(owner)).collection = owner.name
        if files:
            self.layout.separator()
        self.layout.operator(XPLANE_OT_new_file.bl_idname, icon="ADD")


class XPLANE_OT_show_file(bpy.types.Operator):
    """Show this file's settings in the Export panel"""

    bl_idname = "xplane.show_file"
    bl_label = "Show File"
    bl_options = {"INTERNAL"}

    collection: bpy.props.StringProperty()

    def execute(self, context):
        state(context).file_index = bpy.data.collections.find(self.collection)
        return {"FINISHED"}


class XPLANE_OT_toggle_file_type(bpy.types.Operator):
    """Switch this file between cockpit (clickable, panel textures) and aircraft part"""

    bl_idname = "xplane.toggle_file_type"
    bl_label = "Cockpit Or Aircraft Part"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    collection: bpy.props.StringProperty()

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)
        if collection is None:
            return {"CANCELLED"}
        layer = collection.xplane.layer
        layer.export_type = (
            C.EXPORT_TYPE_AIRCRAFT if layer.export_type == C.EXPORT_TYPE_COCKPIT else C.EXPORT_TYPE_COCKPIT
        )
        return {"FINISHED"}


class XPLANE_OT_select_file_objects(bpy.types.Operator):
    """Select the objects of this file"""

    bl_idname = "xplane.select_file_objects"
    bl_label = "Select Objects"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    collection: bpy.props.StringProperty()

    def execute(self, context):
        collection = bpy.data.collections.get(self.collection)
        if collection is None or context.mode != "OBJECT":
            return {"CANCELLED"}
        view_objects = set(context.view_layer.objects)
        for obj in context.view_layer.objects:
            obj.select_set(False)
        chosen = [o for o in collection.all_objects if o in view_objects and o.visible_get()]
        for obj in chosen:
            obj.select_set(True)
        if chosen:
            context.view_layer.objects.active = chosen[0]
        return {"FINISHED"}


class XPLANE_OT_textures_from_materials(bpy.types.Operator):
    """Fill the file's empty texture slots with the images its materials use most. X-Plane draws a whole OBJ with one set of textures"""

    bl_idname = "xplane.textures_from_materials"
    bl_label = "From Materials"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context):
        owner = active_file(context)
        if owner is None:
            return {"CANCELLED"}
        filled = I.textures_from_materials(owner)
        if filled:
            self.report({"INFO"}, "Filled: " + ", ".join(f"{k.replace('texture_', '').replace('texture', 'day')}" for k in filled))
        else:
            self.report({"INFO"}, "Nothing to fill: the slots are set, or the materials have no image textures")
        return {"FINISHED"}


class XPLANE_OT_check(bpy.types.Operator):
    """List what is not filled in yet in the export files. None of it stops an export"""

    bl_idname = "xplane.check"
    bl_label = "Check"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        s = state(context)
        s.check_items.clear()
        for name, text in I.unfinished_in_files(context.scene):
            item = s.check_items.add()
            item.object_name, item.text = name, text
        s.checked = True
        return {"FINISHED"}


class XPLANE_OT_select_object(bpy.types.Operator):
    """Select this object"""

    bl_idname = "xplane.select_object"
    bl_label = "Select"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    name: bpy.props.StringProperty()

    def execute(self, context):
        obj = bpy.data.objects.get(self.name)
        if obj is None or obj.name not in context.view_layer.objects or context.mode != "OBJECT":
            return {"CANCELLED"}
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {"FINISHED"}


class XPLANE_OT_set_light_kind(bpy.types.Operator):
    """Set what kind of X-Plane light the selected lights are"""

    bl_idname = "xplane.set_light_kind"
    bl_label = "Set Light Kind"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    kind: bpy.props.StringProperty()

    def execute(self, context):
        lights = [o for o in _selected_or_active(context) if o.type == "LIGHT"]
        for obj in lights:
            obj.data.xplane.type = self.kind
            if self.kind in (C.LIGHT_SPILL_CUSTOM, C.LIGHT_AUTOMATIC) and obj.data.type not in ("POINT", "SPOT"):
                obj.data.type = "SPOT"
        return {"FINISHED"} if lights else {"CANCELLED"}


LIGHT_KINDS = (
    (C.LIGHT_AUTOMATIC, "Library Light", "A light from X-Plane's lights.txt; color, cone and direction come from the Blender light"),
    (C.LIGHT_SPILL_CUSTOM, "Spill", "Lights up the surfaces around it (cockpit flood lights, panel lights)"),
    (C.LIGHT_CUSTOM, "Glow Sprite", "A halo drawn from part of the texture; it lights nothing"),
    (C.LIGHT_NAMED, "Library Light By Name", "A lights.txt light with no parameters"),
    (C.LIGHT_PARAM, "Library Light, Typed Parameters", "A lights.txt light with its parameters typed by hand"),
    (C.LIGHT_NON_EXPORTING, "Not Exported", "Only for the Blender scene"),
)


def light_kind_label(light_type: str) -> str:
    for kind, label, _ in LIGHT_KINDS:
        if kind == light_type:
            return label
    return "Old X-Plane 9 light"


class XPLANE_MT_light_kind(bpy.types.Menu):
    bl_idname = "XPLANE_MT_light_kind"
    bl_label = "Kind Of Light"

    def draw(self, context):
        for kind, label, help in LIGHT_KINDS:
            self.layout.operator(XPLANE_OT_set_light_kind.bl_idname, text=label).kind = kind


class XPLANE_OT_add_click_zone(bpy.types.Operator):
    """Add an invisible box that can be clicked in X-Plane, at the 3D cursor"""

    bl_idname = "xplane.add_click_zone"
    bl_label = "Click Zone"
    bl_options = {"REGISTER", "UNDO"}

    size: bpy.props.FloatProperty(name="Size", default=0.02, min=0.001, unit="LENGTH")

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(size=self.size, location=context.scene.cursor.location)
        obj = context.active_object
        obj.name = "click zone"
        material = bpy.data.materials.get("X-Plane Click Zone")
        if material is None:
            material = bpy.data.materials.new("X-Plane Click Zone")
            material.xplane.draw = False
            material.diffuse_color = (1.0, 0.3, 0.1, 0.35)
        obj.data.materials.append(material)
        obj.display_type = "WIRE"
        obj.show_in_front = True
        manip = obj.xplane.manip
        manip.enabled = True
        manip.type = C.MANIP_COMMAND
        manip.cursor = C.MANIP_CURSOR_BUTTON
        return {"FINISHED"}


class XPLANE_OT_add_light(bpy.types.Operator):
    """Add an X-Plane light at the 3D cursor"""

    bl_idname = "xplane.add_light"
    bl_label = "Light"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(items=[(k, l, h) for k, l, h in LIGHT_KINDS[:3]])

    def execute(self, context):
        data = bpy.data.lights.new(light_kind_label(self.kind).lower(), "SPOT" if self.kind != C.LIGHT_CUSTOM else "POINT")
        data.xplane.type = self.kind
        obj = bpy.data.objects.new(data.name, data)
        obj.location = context.scene.cursor.location
        context.collection.objects.link(obj)
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {"FINISHED"}


class XPLANE_OT_add_attachment(bpy.types.Operator):
    """Add an empty that X-Plane uses as a wheel, tablet mount or particle emitter, at the 3D cursor"""

    bl_idname = "xplane.add_attachment"
    bl_label = "Attachment Point"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(
        items=(
            (C.EMPTY_USAGE_WHEEL, "Wheel", "Where a landing gear wheel is drawn"),
            (C.EMPTY_USAGE_MAGNET, "Tablet Mount", "Where a VR tablet can be attached"),
            (C.EMPTY_USAGE_EMITTER_PARTICLE, "Particle Emitter", "Where particles (smoke, sparks) come from"),
        )
    )

    def execute(self, context):
        obj = bpy.data.objects.new(self.kind.replace("_", " "), None)
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = 0.1
        obj.location = context.scene.cursor.location
        obj.xplane.special_empty_props.special_type = self.kind
        context.collection.objects.link(obj)
        for other in context.selected_objects:
            other.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {"FINISHED"}


class XPLANE_MT_add(bpy.types.Menu):
    bl_idname = "XPLANE_MT_add"
    bl_label = "X-Plane"

    def draw(self, context):
        layout = self.layout
        layout.operator(XPLANE_OT_add_click_zone.bl_idname, icon="RESTRICT_SELECT_OFF")
        layout.separator()
        for kind, label, _ in LIGHT_KINDS[:3]:
            layout.operator(XPLANE_OT_add_light.bl_idname, text=f"Light: {label}", icon="LIGHT").kind = kind
        layout.separator()
        for kind, label in (
            (C.EMPTY_USAGE_WHEEL, "Wheel"),
            (C.EMPTY_USAGE_MAGNET, "Tablet Mount"),
            (C.EMPTY_USAGE_EMITTER_PARTICLE, "Particle Emitter"),
        ):
            layout.operator(XPLANE_OT_add_attachment.bl_idname, text=label, icon="EMPTY_ARROWS").kind = kind


class XPLANE_MT_object_context(bpy.types.Menu):
    bl_idname = "XPLANE_MT_object_context"
    bl_label = "X-Plane"

    def draw(self, context):
        layout = self.layout
        layout.menu(XPLANE_MT_control_kind.bl_idname, text="Make Clickable As", icon="RESTRICT_SELECT_OFF")
        layout.separator()
        layout.operator(xplane_anim_presets.XPLANE_OT_anim_push_button.bl_idname, text="Animate As Push Button")
        layout.operator(xplane_anim_presets.XPLANE_OT_anim_switch.bl_idname, text="Animate As Switch")
        layout.operator(xplane_anim_presets.XPLANE_OT_anim_range.bl_idname, text="Animate As Knob / Lever")
        layout.separator()
        layout.menu(XPLANE_MT_move_to_file.bl_idname, icon="FILE")


def _add_menu_entry(self, context):
    self.layout.menu(XPLANE_MT_add.bl_idname, icon="AUTO")


def _context_menu_entry(self, context):
    self.layout.separator()
    self.layout.menu(XPLANE_MT_object_context.bl_idname, icon="AUTO")


# ---- Panels: Selected ----------------------------------------------------------------------------------------------
class _Sidebar:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY


def _line_width(icon: str) -> int:
    """About how many characters fit across the sidebar"""
    region = bpy.context.region
    if region is None or region.width < 50:
        return 44
    scale = bpy.context.preferences.system.ui_scale or 1.0
    return max(16, int(region.width / (7.0 * scale)) - (6 if icon != "NONE" else 3))


def _wrapped(layout, text: str, icon: str = "NONE") -> None:
    """Labels do not wrap, so long text is cut into lines that fit"""
    width = _line_width(icon)
    words, line, first = text.split(), "", True
    col = layout.column(align=True)
    for word in words:
        if line and len(line) + len(word) + 1 > width:
            col.label(text=line, icon=icon if first else "BLANK1")
            line, first = word, False
        else:
            line = f"{line} {word}".strip()
    if line:
        col.label(text=line, icon=icon if first else ("BLANK1" if icon != "NONE" else "NONE"))


TYPE_ICONS = {"MESH": "MESH_DATA", "LIGHT": "LIGHT", "EMPTY": "EMPTY_DATA", "ARMATURE": "ARMATURE_DATA"}


class XPLANE_PT_selected(_Sidebar, bpy.types.Panel):
    bl_label = ""
    bl_order = 0

    def draw_header(self, context):
        obj = context.active_object
        if obj is not None:
            self.layout.label(text=obj.name, icon=TYPE_ICONS.get(obj.type, "OBJECT_DATA"))
        else:
            self.layout.label(text="Nothing Selected")

    def draw_header_preset(self, context):
        # Puts the sidebar on the other side of the viewport
        self.layout.operator("screen.region_flip", text="", icon="ARROW_LEFTRIGHT", emboss=False)

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        scene = context.scene
        if obj is None:
            _wrapped(layout, "Click something in the viewport to see and change what it does in X-Plane.", "INFO")
            layout.menu(XPLANE_MT_add.bl_idname, text="Add X-Plane Object", icon="ADD")
            return

        _wrapped(layout, " · ".join(I.summary(obj)))
        selected = context.selected_objects
        if len(selected) > 1:
            counts: Dict[str, int] = {}
            for o in selected:
                word = I.summary(o)[0]
                counts[word] = counts.get(word, 0) + 1
            layout.label(
                text=f"{len(selected)} selected: " + ", ".join(f"{n} {w.lower()}" for w, n in sorted(counts.items())),
                icon="RESTRICT_SELECT_OFF",
            )

        owners = I.files_of(obj, scene)
        if obj.type not in ("MESH", "LIGHT", "EMPTY", "ARMATURE"):
            layout.label(text="X-Plane does not use this kind of object", icon="INFO")
        elif not owners:
            box = layout.box()
            box.label(text="Not exported: it is not in an export file", icon="ERROR")
            row = box.row(align=True)
            row.operator(XPLANE_OT_new_file.bl_idname, text="New File", icon="ADD")
            row.menu(XPLANE_MT_move_to_file.bl_idname, text="Move To File")
        else:
            row = layout.row(align=True)
            for owner in owners:
                if isinstance(owner, bpy.types.Collection):
                    row.operator(
                        XPLANE_OT_show_file.bl_idname, text=f"In {I.file_name(owner)}", icon="FILE"
                    ).collection = owner.name
                else:
                    row.label(text=f"In {I.file_name(owner)}", icon="FILE")
            if not obj.visible_get():
                layout.label(text="Hidden, so it is not exported", icon="HIDE_ON")
        for problem in I.problems(obj, scene, check_file=False):
            _wrapped(layout, problem, "DOT")


class _Card(_Sidebar):
    bl_parent_id = "XPLANE_PT_selected"
    object_types = ("MESH",)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type in cls.object_types


class XPLANE_PT_click(_Card, bpy.types.Panel):
    bl_label = "Clickable"
    bl_order = 1

    def draw_header(self, context):
        self.layout.prop(context.active_object.xplane.manip, "enabled", text="")

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "CLICK")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        manip = obj.xplane.manip
        if not manip.enabled:
            _wrapped(layout, "Not clickable. Pick what it is to make it clickable in the cockpit:")
            layout.menu(XPLANE_MT_control_kind.bl_idname, text="Make Clickable As...", icon="RESTRICT_SELECT_OFF")
            return
        kind = I.control_kind(manip)
        layout.menu(XPLANE_MT_control_kind.bl_idname, text=kind.label)
        _wrapped(layout.column(), kind.help, "INFO")
        col = layout.column()
        for field in I.manip_fields(manip):
            if field.kind in ("command", "dataref"):
                text_with_search(col, manip, field.prop, field.label, field.kind, f"object:xplane.manip.{field.prop}")
            else:
                col.prop(manip, field.prop, text=field.label)
        if I.has_detent_ranges(manip):
            xplane_ui.axis_detent_ranges_layout(col, manip)
        col.separator()
        col.prop(manip, "cursor", text="Cursor")
        if manip.type != C.MANIP_NOOP:
            col.prop(manip, "tooltip", text="Tooltip")


class XPLANE_PT_motion(_Card, bpy.types.Panel):
    bl_label = "Moves"
    bl_order = 2
    object_types = ("MESH", "LIGHT", "EMPTY", "ARMATURE")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        motion = I.motion_datarefs(obj)
        presets = layout.row(align=True)
        presets.operator(xplane_anim_presets.XPLANE_OT_anim_push_button.bl_idname, text="Button")
        presets.operator(xplane_anim_presets.XPLANE_OT_anim_switch.bl_idname, text="Switch")
        presets.operator(xplane_anim_presets.XPLANE_OT_anim_range.bl_idname, text="Knob / Lever")
        if not motion:
            _wrapped(layout, "Not animated. Use a preset above, or key it by hand:")
        for index, dataref in motion:
            box = layout.box()
            row = box.row(align=True)
            row.prop(dataref, "path", text="")
            op = row.operator(XPLANE_OT_search.bl_idname, text="", icon="VIEWZOOM")
            op.kind, op.target = "dataref", f"object:xplane.datarefs[{index}].path"
            row.operator(XPLANE_OT_remove_dataref.bl_idname, text="", icon="X").index = index
            keys = I.dataref_keys(obj, index)
            if keys:
                flow = box.grid_flow(row_major=True, columns=4, align=True)
                for frame, value in keys:
                    current = int(round(frame)) == context.scene.frame_current
                    flow.operator(
                        XPLANE_OT_go_to_frame.bl_idname, text=f"{value:g}", depress=current
                    ).frame = frame
            row = box.row(align=True)
            row.prop(dataref, "value", text="At")
            row.operator(XPLANE_OT_key_pose.bl_idname, text="Key Pose", icon="KEY_HLT").index = index
            box.prop(dataref, "loop", text="Repeats Every")
        layout.operator(XPLANE_OT_add_dataref.bl_idname, text="Key By Hand" if not motion else "Add Dataref", icon="ADD").anim_type = (
            C.ANIM_TYPE_TRANSFORM
        )


class XPLANE_PT_visibility(_Card, bpy.types.Panel):
    bl_label = "Shows / Hides"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}
    object_types = ("MESH", "LIGHT", "EMPTY", "ARMATURE")

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "VISIBILITY")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        rules = I.visibility_datarefs(obj)
        if not rules:
            _wrapped(layout, "Always shown. Add a rule to show or hide it with a dataref:")
        for index, dataref in rules:
            box = layout.box()
            row = box.row(align=True)
            row.prop_enum(dataref, "anim_type", C.ANIM_TYPE_SHOW, text="Show")
            row.prop_enum(dataref, "anim_type", C.ANIM_TYPE_HIDE, text="Hide")
            row.label(text="when")
            row.operator(XPLANE_OT_remove_dataref.bl_idname, text="", icon="X").index = index
            row = box.row(align=True)
            row.prop(dataref, "path", text="")
            op = row.operator(XPLANE_OT_search.bl_idname, text="", icon="VIEWZOOM")
            op.kind, op.target = "dataref", f"object:xplane.datarefs[{index}].path"
            row = box.row(align=True)
            row.prop(dataref, "show_hide_v1", text="is from")
            row.prop(dataref, "show_hide_v2", text="to")
        row = layout.row(align=True)
        row.operator(XPLANE_OT_add_dataref.bl_idname, text="Show When", icon="HIDE_OFF").anim_type = C.ANIM_TYPE_SHOW
        row.operator(XPLANE_OT_add_dataref.bl_idname, text="Hide When", icon="HIDE_ON").anim_type = C.ANIM_TYPE_HIDE


def glow_layout(layout, settings, target: str) -> None:
    layout.active = settings.lightLevel
    _wrapped(layout, "The night (LIT) texture's brightness follows a dataref, like a backlight on a dimmer.")
    text_with_search(layout, settings, "lightLevel_dataref", "Dataref", "dataref", target)
    row = layout.row(align=True)
    row.prop(settings, "lightLevel_v1", text="Off At")
    row.prop(settings, "lightLevel_v2", text="Full At")
    row = layout.row(align=True)
    row.prop(settings, "lightLevel_photometric", text="")
    sub = row.row(align=True)
    sub.active = settings.lightLevel_photometric
    sub.prop(settings, "lightLevel_brightness", text="Full (nits)")


class XPLANE_PT_glow(_Card, bpy.types.Panel):
    bl_label = "Glow"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.prop(context.active_object.xplane, "lightLevel", text="")

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "GLOW")

    def draw(self, context):
        glow_layout(self.layout.column(), context.active_object.xplane, "object:xplane.lightLevel_dataref")


def _automatic_light_layout(layout, obj) -> None:
    data = obj.data
    name = data.xplane.name.strip()
    if not name:
        return
    try:
        parsed = xplane_lights_txt_parser.get_parsed_light(name)
    except KeyError:
        return
    if not xplane_lights_txt_parser.is_automatic_light_compatible(parsed.name):
        _wrapped(layout, "This light cannot be a Library Light: use Library Light By Name or Typed Parameters.", "ERROR")
        return
    for param, prop in (
        ("INDEX", "param_index"),
        ("INTENSITY", "param_intensity_new"),
        ("FREQ", "param_freq"),
        ("PHASE", "param_phase"),
        ("SIZE", "param_size"),
    ):
        if param == "SIZE" and parsed.name in xplane_lights_txt_parser.SIZE_AS_INTENSITY:
            prop = "param_intensity_new"
        if param in parsed.light_param_def:
            layout.prop(data.xplane, prop)
    if data.type not in ("POINT", "SPOT"):
        layout.label(text="Use a Point or Spot light", icon="ERROR")
    else:
        layout.label(text="Color and cone come from the Blender light", icon="INFO")


class XPLANE_PT_light(_Card, bpy.types.Panel):
    bl_label = "Light"
    bl_order = 1
    object_types = ("LIGHT",)

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "LIGHT")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        data = obj.data
        x = data.xplane
        layout.menu(XPLANE_MT_light_kind.bl_idname, text=light_kind_label(x.type), icon="LIGHT")
        col = layout.column()
        if x.type == C.LIGHT_AUTOMATIC:
            xplane_ui.light_name_rows(col, data)
            _automatic_light_layout(col, obj)
        elif x.type == C.LIGHT_SPILL_CUSTOM:
            col.prop(x, "size", text="Reach (m)")
            text_with_search(col, x, "dataref", "Brightness Dataref", "dataref", "light:xplane.dataref")
            col.prop(data, "color")
            if data.type not in ("POINT", "SPOT"):
                col.label(text="Use a Point or Spot light", icon="ERROR")
            else:
                col.label(text="Cone comes from the Blender light", icon="INFO")
        elif x.type == C.LIGHT_CUSTOM:
            col.prop(x, "size")
            col.prop(x, "uv", text="Texture Area")
            text_with_search(col, x, "dataref", "Dataref", "dataref", "light:xplane.dataref")
            col.prop(x, "enable_rgb_override", text="Type The Color")
            if x.enable_rgb_override:
                col.prop(x, "rgb_override_values", text="")
            else:
                col.prop(data, "color")
            col.prop(data, "energy", text="Alpha")
        elif x.type == C.LIGHT_NAMED:
            xplane_ui.light_name_rows(col, data)
        elif x.type == C.LIGHT_PARAM:
            xplane_ui.light_name_rows(col, data)
            col.prop(x, "params")
            wanted, problem = xplane_light_tools.param_check(x.name, x.params)
            if wanted:
                col.label(text="In order: " + " ".join(wanted))
            if problem:
                col.label(text=problem, icon="ERROR")
        elif x.type in xplane_xp12.LEGACY_LIGHT_TYPES:
            _wrapped(col, "An X-Plane 9 light. It still exports as before; pick a kind above to modernize it.", "INFO")
        if x.type != C.LIGHT_NON_EXPORTING:
            layout.operator(
                xplane_light_tools.XPLANE_OT_lights_preview.bl_idname, text="Preview As In X-Plane", icon="SHADING_RENDERED"
            ).selected_only = True


class XPLANE_PT_attachment(_Card, bpy.types.Panel):
    bl_label = "Attachment Point"
    bl_order = 1
    object_types = ("EMPTY",)

    def draw_header_preset(self, context):
        copy_button(self.layout, context, "ATTACHMENT")

    def draw(self, context):
        xplane_ui.empty_layout(self.layout, context.active_object)


BLEND_LABELS = ((C.BLEND_ON, "Smooth"), (C.BLEND_OFF, "Hard Edge"), (C.BLEND_SHADOW, "Cut Shadow"))
SCREEN_LABELS = ((C.COCKPIT_FEATURE_NONE, "None"), (C.COCKPIT_FEATURE_PANEL, "2D Panel"), (C.COCKPIT_FEATURE_DEVICE, "Avionics"))


class XPLANE_PT_surface(_Card, bpy.types.Panel):
    bl_label = "Surface"
    bl_order = 5

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH"

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        layout.template_ID(obj, "active_material", new="material.new")
        material = obj.active_material
        if material is None:
            layout.label(text="No material: exported with the default look", icon="INFO")
            return
        # Each mesh using the material is one user
        users = material.users - (1 if material.use_fake_user else 0)
        if users > 1:
            layout.label(text=f"Shared by {users} meshes: changes apply to all", icon="LINKED")
        m = material.xplane
        col = layout.column()
        col.prop(m, "draw", text="Visible")
        if not m.draw:
            col.label(text="Invisible, still clickable", icon="INFO")
        if m.draw:
            col.label(text="Transparency")
            row = col.row(align=True)
            for value, label in BLEND_LABELS:
                row.prop_enum(m, "blend_v1000", value, text=label)
            if m.blend_v1000 in (C.BLEND_OFF, C.BLEND_SHADOW):
                col.prop(m, "blendRatio", text="Cut Off Below", slider=True)
            col.prop(m, "shadow_local", text="Casts Shadows")
        col.prop(m, "solid_camera", text="Camera Cannot Pass Through")

        col.separator()
        col.label(text="Screen")
        row = col.row(align=True)
        for value, label in SCREEN_LABELS:
            row.prop_enum(m, "cockpit_feature", value, text=label)
        if m.cockpit_feature == C.COCKPIT_FEATURE_PANEL:
            owners = I.files_of(obj, context.scene)
            if owners and owners[0].xplane.layer.cockpit_panel_mode == C.PANEL_COCKPIT_REGION:
                col.prop(m, "cockpit_region", text="Panel Region")
            else:
                _wrapped(col, "Shows the aircraft's 2D panel, mapped by the UVs.", "INFO")
        elif m.cockpit_feature == C.COCKPIT_FEATURE_DEVICE:
            col.prop(m, "device_name", text="Device")
            if m.device_name == C.DEVICE_PLUGIN:
                col.prop(m, "plugin_device")
            col.label(text="Powered By")
            grid = col.grid_flow(row_major=True, columns=3, align=True)
            for bus in range(6):
                grid.prop(m, f"device_bus_{bus}", toggle=True)
            col.prop(m, "device_lighting_channel", text="Brightness Knob (Channel)")
            col.prop(m, "device_auto_adjust", text="Brighter In Daylight")
        if m.cockpit_feature != C.COCKPIT_FEATURE_NONE:
            row = col.row(align=True)
            row.prop(m, "cockpit_feature_use_luminance", text="")
            sub = row.row()
            sub.active = m.cockpit_feature_use_luminance
            sub.prop(m, "cockpit_feature_luminance", text="Max Brightness (nits)")

        col.separator()
        row = col.row()
        row.prop(m, "lightLevel", text="Material Glow")
        if m.lightLevel:
            glow_layout(col.box().column(), m, "material:xplane.lightLevel_dataref")


class XPLANE_PT_surface_more(_Sidebar, bpy.types.Panel):
    bl_label = "More Surface Settings"
    bl_parent_id = "XPLANE_PT_surface"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == "MESH" and obj.active_material is not None

    def draw(self, context):
        layout = self.layout
        material = context.active_object.active_material
        m = material.xplane
        col = layout.column()
        col.prop(m, "surfaceType", text="Hard Surface")
        if m.surfaceType != C.SURFACE_TYPE_NONE:
            col.prop(m, "deck", text="Can Be Under It (deck)")
        col.prop(m, "poly_os", text="Draw On Top (polygon offset)")
        xplane_ui.custom_layout(col, material)
        if len(m.conditions):
            xplane_ui.conditions_layout(col, material)


class XPLANE_PT_more(_Card, bpy.types.Panel):
    bl_label = "Advanced"
    bl_order = 9
    bl_options = {"DEFAULT_CLOSED"}
    object_types = ("MESH", "LIGHT", "EMPTY", "ARMATURE")

    def draw(self, context):
        layout = self.layout
        obj = context.active_object
        x = obj.xplane
        col = layout.column()
        if obj.type == "MESH":
            col.prop(x, "hud_glass", text="HUD Glass")
            col.prop(x, "rain_cannot_escape", text="Rain Cannot Escape")
        row = col.row(align=True)
        row.prop(x, "override_weight", text="Draw Order")
        sub = row.row()
        sub.active = x.override_weight
        sub.prop(x, "weight", text="")
        owners = I.files_of(obj, context.scene)
        lods = int(owners[0].xplane.layer.lods) if owners else 0
        if lods:
            col.prop(x, "override_lods", text="Only In Some Distances")
            if x.override_lods:
                grid = col.grid_flow(row_major=True, columns=2, align=True)
                for i, bucket in enumerate(owners[0].xplane.layer.lod[:lods]):
                    grid.prop(x, "lod", index=i, text=f"{bucket.near}-{bucket.far} m", toggle=True)
        if obj.type != "EMPTY":
            xplane_ui.custom_layout(col, obj)
        if len(x.conditions):
            xplane_ui.conditions_layout(col, obj)


class XPLANE_PT_every_setting(_Sidebar, bpy.types.Panel):
    bl_label = "Every Setting (Classic)"
    bl_parent_id = "XPLANE_PT_more"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        fake = SimpleNamespace(layout=self.layout.column())
        obj = context.active_object
        xplane_ui.OBJECT_PT_xplane.draw(fake, context)
        if obj.type in ("LIGHT", "EMPTY"):
            xplane_ui.DATA_PT_xplane.draw(fake, context)
        if obj.type == "MESH" and obj.active_material is not None:
            fake.layout.separator()
            fake.layout.label(text=f"Material '{obj.active_material.name}'", icon="MATERIAL")
            xplane_ui.MATERIAL_PT_xplane.draw(fake, context)


# ---- Panels: Export ---------------------------------------------------------------------------------------------
class XPLANE_UL_files(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        collection = item
        layer = collection.xplane.layer
        row = layout.row(align=True)
        row.prop(collection.xplane, "is_exportable_collection", text="", icon="EXPORT", emboss=False)
        sub = row.row(align=True)
        sub.active = collection.xplane.is_exportable_collection
        sub.label(text=I.file_name(collection))
        if collection.xplane.is_exportable_collection:
            cockpit = layer.export_type == C.EXPORT_TYPE_COCKPIT
            sub.operator(
                XPLANE_OT_toggle_file_type.bl_idname,
                text="Cockpit" if cockpit else "Part",
                emboss=False,
            ).collection = collection.name
            sub.operator(
                XPLANE_OT_select_file_objects.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False
            ).collection = collection.name

    def draw_filter(self, context, layout):
        layout.prop(state(context), "show_all_collections")
        layout.prop(self, "filter_name", text="")

    def filter_items(self, context, data, propname):
        collections = getattr(data, propname)
        in_scene = set(c.name for c in xplane_helpers.get_collections_in_scene(context.scene)[1:])
        show_all = state(context).show_all_collections
        needle = self.filter_name.lower()
        flags = []
        for c in collections:
            # Collections with export settings, such as imported OBJs, are listed unticked: one click exports them
            set_up = c.xplane.is_exportable_collection or bool(c.xplane.layer.name.strip())
            shown = c.name in in_scene and (show_all or set_up)
            if shown and needle:
                shown = needle in c.name.lower() or needle in c.xplane.layer.name.lower()
            flags.append(self.bitflag_filter_item if shown else 0)
        return flags, []


class XPLANE_PT_export(_Sidebar, bpy.types.Panel):
    bl_label = "Export"
    bl_order = 1

    def draw_header_preset(self, context):
        self.layout.label(text="X-Plane 12")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        files = I.export_files(scene)
        layout.template_list(
            "XPLANE_UL_files", "", bpy.data, "collections", state(context), "file_index", rows=max(2, min(len(files), 8))
        )
        roots = [f for f in files if isinstance(f, bpy.types.Object)]
        for root in roots:
            row = layout.row(align=True)
            row.operator(XPLANE_OT_select_object.bl_idname, text=f"{I.file_name(root)} (root object)", icon="OBJECT_DATA").name = root.name
        row = layout.row(align=True)
        row.operator(XPLANE_OT_new_file.bl_idname, text="New File From Selection", icon="ADD")

        col = layout.column()
        col.scale_y = 1.5
        if not bpy.data.filepath:
            col.enabled = False
            col.operator("scene.export_to_relative_dir", text="Save The .blend First", icon="EXPORT")
            layout.label(text="OBJs are written next to the .blend file", icon="INFO")
            return
        col.enabled = bool(files)
        col.operator("scene.export_to_relative_dir", text=f"Export {len(files)} File{'s' if len(files) != 1 else ''}", icon="EXPORT")
        layout.label(text=f"To {bpy.path.abspath('//')}", icon="FILE_FOLDER")


def _layer_textures(layout, layer) -> None:
    col = layout.column(align=True)
    col.prop(layer, "texture", text="Day")
    col.prop(layer, "texture_lit", text="Night")
    col.prop(layer, "texture_normal", text="Normal")
    layout.operator(XPLANE_OT_textures_from_materials.bl_idname, icon="MATERIAL")


class _FilePanel(_Sidebar):
    bl_parent_id = "XPLANE_PT_export"

    @classmethod
    def poll(cls, context):
        return active_file(context) is not None


class XPLANE_PT_file(_FilePanel, bpy.types.Panel):
    bl_label = ""
    bl_order = 1

    def draw_header(self, context):
        owner = active_file(context)
        self.layout.label(text=f"File: {I.file_name(owner)}")

    def draw(self, context):
        layout = self.layout
        owner = active_file(context)
        layer = owner.xplane.layer
        col = layout.column()
        col.prop(layer, "name", text="Saved As")
        row = col.row(align=True)
        row.prop_enum(layer, "export_type", C.EXPORT_TYPE_AIRCRAFT, text="Aircraft Part")
        row.prop_enum(layer, "export_type", C.EXPORT_TYPE_COCKPIT, text="Cockpit")
        if layer.export_type not in xplane_xp12.FILE_TYPES:
            col.label(text="Scenery is not supported: pick one of the above", icon="ERROR")

        box = layout.box()
        box.label(text="Textures", icon="TEXTURE")
        _layer_textures(box, layer)

        box = layout.box()
        box.label(text="Look", icon="SHADING_TEXTURE")
        col = box.column()
        col.prop(layer, "blend_glass", text="See-Through Glass")
        col.prop(layer, "normal_metalness", text="Metalness In Normal Map")
        row = col.row(align=True)
        row.prop(layer, "luminance_override", text="")
        sub = row.row()
        sub.active = layer.luminance_override
        sub.prop(layer, "luminance", text="Max Glow (nits)")

        if layer.export_type == C.EXPORT_TYPE_COCKPIT:
            box = layout.box()
            box.label(text="Cockpit Panel", icon="WINDOW")
            col = box.column()
            col.prop(layer, "cockpit_panel_mode", text="Panel Texture")
            if layer.cockpit_panel_mode == C.PANEL_COCKPIT_REGION:
                col.prop(layer, "cockpit_regions", text="Regions")
                for i, region in enumerate(layer.cockpit_region[: int(layer.cockpit_regions)]):
                    sub = col.box().column(align=True)
                    sub.label(text=f"Region {i + 1}")
                    row = sub.row(align=True)
                    row.prop(region, "left")
                    row.prop(region, "top", text="Bottom")
                    row = sub.row(align=True)
                    row.prop(region, "width", text=f"Width 2^ ({2 ** region.width})")
                    row.prop(region, "height", text=f"Height 2^ ({2 ** region.height})")

        box = layout.box()
        box.label(text="Distances (Levels Of Detail)", icon="CON_DISTLIMIT")
        box.prop(layer, "lods", text="Levels")
        for i, lod in enumerate(layer.lod[: int(layer.lods)]):
            row = box.row(align=True)
            row.label(text=f"{i + 1}")
            row.prop(lod, "near")
            row.prop(lod, "far")


class XPLANE_PT_file_more_textures(_FilePanel, bpy.types.Panel):
    bl_label = "X-Plane 12 Texture Maps"
    bl_order = 2
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layer = active_file(context).xplane.layer
        col = self.layout.column(align=True)
        col.prop(layer, "texture_map_normal", text="Normal")
        col.prop(layer, "texture_map_material_gloss", text="Material / Gloss")
        col.prop(layer, "texture_map_gloss", text="Gloss")


class XPLANE_PT_file_rain(_FilePanel, bpy.types.Panel):
    bl_label = "Rain And Wipers"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        owner = active_file(context)
        xplane_ui.rain_layout(layout, owner.xplane.layer, int(xplane_xp12.LATEST_VERSION))
        scene = context.scene
        box = layout.box()
        box.label(text="Wiper Gradient Texture")
        row = box.row()
        row.prop(scene.xplane, "wiper_bake_start")
        row.label(text=f"To Frame {scene.xplane.wiper_bake_start + 254}")
        op = box.operator("xplane.bake_wiper_gradient_texture", text=f"Bake For {I.file_name(owner)}")
        op.start = scene.xplane.wiper_bake_start


class XPLANE_PT_file_detail(_FilePanel, bpy.types.Panel):
    bl_label = "Detail Textures"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        xplane_ui.detail_textures_layout(self.layout, active_file(context).xplane.layer, False)


class XPLANE_PT_file_more(_FilePanel, bpy.types.Panel):
    bl_label = "More"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        owner = active_file(context)
        layer = owner.xplane.layer
        col = layout.column()
        col.prop(layer, "particle_system_file", text="Particle Systems (.pss)")
        col.prop(layer, "slungLoadWeight", text="Slung Load Weight (lb)")
        col.prop(layer, "debug", text="Debug Info In This OBJ")
        version = int(xplane_xp12.LATEST_VERSION)
        xplane_ui.export_path_dir_layer_layout(col, owner, version)
        xplane_ui.custom_layer_layout(col, owner, version)


class XPLANE_PT_export_options(_Sidebar, bpy.types.Panel):
    bl_label = "Options"
    bl_parent_id = "XPLANE_PT_export"
    bl_order = 9
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column()
        col.prop(scene.xplane, "optimize", text="Smaller Files (share vertices)")
        col.prop(scene.xplane, "debug", text="Debug Info")
        if scene.xplane.debug:
            col.prop(scene.xplane, "log")
        prefs = preferences(context)
        if prefs is not None:
            col.prop(prefs, "classic_panels")
        col.label(text=f"Add-on {xplane_helpers.VerStruct.current()}", icon="INFO")
        if scene.xplane.version != xplane_xp12.LATEST_VERSION:
            col.label(text="This scene still targets an older X-Plane", icon="ERROR")
            col.prop(scene.xplane, "version")


# ---- Panels: Unfinished work, Tools ------------------------------------------------------------------------------
class XPLANE_UL_check(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index=0, flt_flag=0):
        row = layout.row(align=True)
        row.operator(XPLANE_OT_select_object.bl_idname, text="", icon="RESTRICT_SELECT_OFF", emboss=False).name = item.object_name
        row.label(text=f"{item.object_name}: {item.text}")


class XPLANE_PT_check(_Sidebar, bpy.types.Panel):
    bl_label = "Unfinished Work"
    bl_order = 2
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        s = state(context)
        row = layout.row()
        row.operator(XPLANE_OT_check.bl_idname, text="Check Again" if s.checked else "Check", icon="VIEWZOOM")
        if not s.checked:
            _wrapped(layout, "Lists what is not filled in yet in the export files. Exports never wait for it: what is missing is left out.")
            return
        if not s.check_items:
            layout.label(text="Nothing unfinished", icon="CHECKMARK")
            return
        layout.label(text=f"{len(s.check_items)} thing(s) to finish")
        layout.template_list("XPLANE_UL_check", "", s, "check_items", s, "check_index", rows=6)


class XPLANE_PT_tools(_Sidebar, bpy.types.Panel):
    bl_label = "Tools"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(state(context), "show_click_zones", toggle=True, icon="RESTRICT_SELECT_OFF")
        row.prop(state(context), "click_labels", text="")
        layout.operator(
            xplane_light_tools.XPLANE_OT_lights_preview.bl_idname, text="Preview Every Light As In X-Plane", icon="LIGHT"
        ).selected_only = False


# ---- Registration -----------------------------------------------------------------------------------------------
_classes = (
    XPlaneAddonPreferences,
    XPlaneCheckItem,
    XPlaneSidebarState,
    XPLANE_OT_search,
    XPLANE_OT_set_control_kind,
    XPLANE_MT_control_kind,
    XPLANE_OT_copy_to_selected,
    XPLANE_OT_add_dataref,
    XPLANE_OT_remove_dataref,
    XPLANE_OT_key_pose,
    XPLANE_OT_go_to_frame,
    XPLANE_OT_new_file,
    XPLANE_OT_move_to_file,
    XPLANE_MT_move_to_file,
    XPLANE_OT_show_file,
    XPLANE_OT_toggle_file_type,
    XPLANE_OT_select_file_objects,
    XPLANE_OT_textures_from_materials,
    XPLANE_OT_check,
    XPLANE_OT_select_object,
    XPLANE_OT_set_light_kind,
    XPLANE_MT_light_kind,
    XPLANE_OT_add_click_zone,
    XPLANE_OT_add_light,
    XPLANE_OT_add_attachment,
    XPLANE_MT_add,
    XPLANE_MT_object_context,
    XPLANE_PT_selected,
    XPLANE_PT_click,
    XPLANE_PT_light,
    XPLANE_PT_attachment,
    XPLANE_PT_motion,
    XPLANE_PT_visibility,
    XPLANE_PT_glow,
    XPLANE_PT_surface,
    XPLANE_PT_surface_more,
    XPLANE_PT_more,
    XPLANE_PT_every_setting,
    XPLANE_UL_files,
    XPLANE_PT_export,
    XPLANE_PT_file,
    XPLANE_PT_file_more_textures,
    XPLANE_PT_file_rain,
    XPLANE_PT_file_detail,
    XPLANE_PT_file_more,
    XPLANE_PT_export_options,
    XPLANE_UL_check,
    XPLANE_PT_check,
    XPLANE_PT_tools,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.xplane_sidebar = bpy.props.PointerProperty(type=XPlaneSidebarState)
    bpy.types.VIEW3D_MT_add.append(_add_menu_entry)
    bpy.types.VIEW3D_MT_object_context_menu.append(_context_menu_entry)


def unregister():
    bpy.types.VIEW3D_MT_object_context_menu.remove(_context_menu_entry)
    bpy.types.VIEW3D_MT_add.remove(_add_menu_entry)
    del bpy.types.WindowManager.xplane_sidebar
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
