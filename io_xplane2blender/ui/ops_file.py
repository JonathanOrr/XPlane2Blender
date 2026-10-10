"""
Operators for export files: making them, moving objects into them, checking what is unfinished.
"""

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender import xplane_inspector as I

from .state import active_file, state


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
            self.name = context.object.name if context.object else "new_object"
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        cockpit = None if self.file_type == "AUTO" else self.file_type == C.EXPORT_TYPE_COCKPIT
        name = self.name.strip() or "new_object"
        collection = I.move_into_new_file(context.selected_objects, name, context.scene, cockpit)
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
        inside = [
            c
            for owner in I.export_files(context.scene)
            if isinstance(owner, bpy.types.Collection)
            for c in (owner, *owner.children_recursive)
        ]
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


class XPLANE_OT_show_file(bpy.types.Operator):
    """Show this file's settings in the Scene tab's X-Plane Export panel"""

    bl_idname = "xplane.show_file"
    bl_label = "Show File"
    bl_options = {"INTERNAL"}

    collection: bpy.props.StringProperty()
    # A root object is a file too. Its settings are shown when it is the active object
    root_object: bpy.props.StringProperty()

    def execute(self, context):
        state(context).file_index = bpy.data.collections.find(self.collection)
        root = bpy.data.objects.get(self.root_object) if self.root_object else None
        if root is not None and root.name in context.view_layer.objects and context.mode == "OBJECT":
            for other in context.selected_objects:
                other.select_set(False)
            root.select_set(True)
            context.view_layer.objects.active = root
        space = context.space_data
        if space is not None and space.type == "PROPERTIES":
            space.context = "SCENE"
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
        cockpit = layer.export_type == C.EXPORT_TYPE_COCKPIT
        layer.export_type = C.EXPORT_TYPE_AIRCRAFT if cockpit else C.EXPORT_TYPE_COCKPIT
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
            names = (owner.xplane.layer.bl_rna.properties[k].name for k in filled)
            self.report({"INFO"}, "Filled: " + ", ".join(names))
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


classes = (
    XPLANE_OT_new_file,
    XPLANE_OT_move_to_file,
    XPLANE_OT_show_file,
    XPLANE_OT_toggle_file_type,
    XPLANE_OT_select_file_objects,
    XPLANE_OT_textures_from_materials,
    XPLANE_OT_check,
)
