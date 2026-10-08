"""
Bulk editing of the X-Plane text settings of many objects at once: commands, datarefs, light level datarefs,
tooltips and custom attribute values.

A cockpit has hundreds of controls that differ only by side or number ("mcdu/key/A" and "mcdu_2/key/A",
"capt_nd_brightness" and "fo_nd_brightness"). Find and Replace changes a list of text pairs across the selection
in one step, and Duplicate and Replace copies a finished panel and renames everything on the copy, so the right
hand side never has to be typed again.

The settings live on the window manager, so they are not saved in the .blend and the data model is unchanged.
"""

import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterator, List, Optional, Sequence, Set, Tuple

import bpy

from .xplane_properties_panel import Properties, compact_grid, compact_row

KINDS = (
    ("COMMANDS", "Commands", "Manipulator commands"),
    ("DATAREFS", "Datarefs", "Animation, manipulator and light datarefs, and light parameters"),
    ("LIGHT_LEVELS", "Light Levels", "Light level datarefs of objects and materials"),
    ("TOOLTIPS", "Tooltips", "Manipulator tooltips"),
    ("CUSTOM", "Custom Attributes", "Values of custom attributes and custom animation attributes"),
)
ALL_KINDS = frozenset(k for k, _, _ in KINDS)


@dataclass
class Field:
    """One text setting of an object: setting it writes owner.attribute"""

    obj: bpy.types.Object
    owner: object
    attribute: str
    kind: str
    label: str  # Where it is, for the preview: "MCDU_KEY_A: command"
    shared_id: Optional[bpy.types.ID] = None  # A material, light or armature that other objects may also use


@dataclass
class Change:
    field: Field
    old: str
    new: str


def _object_fields(obj: bpy.types.Object) -> Iterator[Field]:
    x = obj.xplane
    name = obj.name
    if x.manip.enabled:
        for attribute in ("command", "positive_command", "negative_command"):
            yield Field(obj, x.manip, attribute, "COMMANDS", f"{name}: {attribute.replace('_', ' ')}")
        for attribute in ("dataref1", "dataref2"):
            yield Field(obj, x.manip, attribute, "DATAREFS", f"{name}: manipulator {attribute}")
        yield Field(obj, x.manip, "tooltip", "TOOLTIPS", f"{name}: tooltip")
    for i, dataref in enumerate(x.datarefs):
        yield Field(obj, dataref, "path", "DATAREFS", f"{name}: animation dataref {i + 1}")
    if x.lightLevel:
        yield Field(obj, x, "lightLevel_dataref", "LIGHT_LEVELS", f"{name}: light level")
    for attr in x.customAttributes:
        yield Field(obj, attr, "value", "CUSTOM", f"{name}: {attr.name or 'custom attribute'}")
    for attr in x.customAnimAttributes:
        yield Field(obj, attr, "value", "CUSTOM", f"{name}: {attr.name or 'custom animation attribute'}")

    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        if mat.xplane.lightLevel:
            yield Field(obj, mat.xplane, "lightLevel_dataref", "LIGHT_LEVELS", f"material {mat.name}: light level", mat)
        for attr in mat.xplane.customAttributes:
            yield Field(obj, attr, "value", "CUSTOM", f"material {mat.name}: {attr.name or 'custom attribute'}", mat)

    if obj.type == "LIGHT" and obj.data is not None:
        light = obj.data
        yield Field(obj, light.xplane, "dataref", "DATAREFS", f"{name}: light dataref", light)
        yield Field(obj, light.xplane, "params", "DATAREFS", f"{name}: light parameters", light)
        for attr in light.xplane.customAttributes:
            yield Field(obj, attr, "value", "CUSTOM", f"{name}: {attr.name or 'custom attribute'}", light)

    if obj.type == "ARMATURE" and obj.data is not None:
        for bone in obj.data.bones:
            for i, dataref in enumerate(bone.xplane.datarefs):
                yield Field(obj, dataref, "path", "DATAREFS", f"{name}/{bone.name}: animation dataref {i + 1}", obj.data)
            for attr in bone.xplane.customAnimAttributes:
                yield Field(obj, attr, "value", "CUSTOM", f"{name}/{bone.name}: {attr.name}", obj.data)


def make_replacer(
    pairs: Sequence[Tuple[str, str]], use_regex: bool, match_case: bool
) -> Callable[[str], str]:
    """
    A function that applies every (find, replace) pair to a text, in order. Pairs with an empty find are ignored.
    Raises re.error for a bad regular expression
    """
    flags = 0 if match_case else re.IGNORECASE
    compiled = []
    for find, replace in pairs:
        if not find:
            continue
        if use_regex:
            compiled.append((re.compile(find, flags), replace))
        else:
            # The replacement is literal text, so a backslash in it must not be read as a group reference
            compiled.append((re.compile(re.escape(find), flags), replace.replace("\\", "\\\\")))

    def replacer(text: str) -> str:
        for pattern, replace in compiled:
            text = pattern.sub(replace, text)
        return text

    return replacer


def plan(
    objects: Sequence[bpy.types.Object],
    pairs: Sequence[Tuple[str, str]],
    kinds: Set[str] = ALL_KINDS,
    use_regex: bool = False,
    match_case: bool = True,
) -> Tuple[List[Change], List[bpy.types.ID]]:
    """
    Every change the pairs would make to the objects, and the shared materials, lights and armatures that are
    left alone because objects outside the list use them too (changing those would change the other side as well)
    """
    replacer = make_replacer(pairs, use_regex, match_case)
    if not any(find for find, _ in pairs):
        return [], []
    targets = set(objects)
    users: Dict[bpy.types.ID, Set[bpy.types.Object]] = {}
    for obj in bpy.data.objects:
        if obj.data is not None and obj.type in ("LIGHT", "ARMATURE"):
            users.setdefault(obj.data, set()).add(obj)
        for slot in obj.material_slots:
            if slot.material is not None:
                users.setdefault(slot.material, set()).add(obj)

    changes: List[Change] = []
    skipped: List[bpy.types.ID] = []
    seen: Set[Tuple[int, str]] = set()
    for obj in objects:
        for field in _object_fields(obj):
            if field.kind not in kinds:
                continue
            key = (field.owner.as_pointer(), field.attribute)
            if key in seen:  # A material used by two selected objects is changed once
                continue
            seen.add(key)
            old = getattr(field.owner, field.attribute)
            if not old:
                continue
            new = replacer(old)
            if new == old:
                continue
            if field.shared_id is not None and not users.get(field.shared_id, set()) <= targets:
                if field.shared_id not in skipped:
                    skipped.append(field.shared_id)
                continue
            changes.append(Change(field, old, new))
    return changes, skipped


def apply(changes: Sequence[Change]) -> None:
    for change in changes:
        setattr(change.field.owner, change.field.attribute, change.new)


# ---- Blender UI -----------------------------------------------------------------------------------------------


class XPlaneBulkEditPair(bpy.types.PropertyGroup):
    find: bpy.props.StringProperty(name="Find", description="Text to find")
    replace: bpy.props.StringProperty(name="Replace", description="Text to put in its place")


class XPlaneBulkEditSettings(bpy.types.PropertyGroup):
    pairs: bpy.props.CollectionProperty(type=XPlaneBulkEditPair)
    scope: bpy.props.EnumProperty(
        name="Objects",
        items=(
            ("SELECTED", "Selected", "The selected objects"),
            ("SELECTED_CHILDREN", "Selected And Children", "The selected objects and everything parented below them"),
            ("SCENE", "Whole Scene", "Every object in the scene"),
        ),
        default="SELECTED",
    )
    kinds: bpy.props.EnumProperty(
        name="Settings",
        items=KINDS,
        options={"ENUM_FLAG"},
        default=set(ALL_KINDS),
    )
    use_regex: bpy.props.BoolProperty(
        name="Regular Expressions",
        description="Read Find as a regular expression, Replace may use \\1 for groups",
        default=False,
    )
    match_case: bpy.props.BoolProperty(
        name="Match Case", description="Datarefs and commands are case sensitive in X-Plane", default=True
    )
    show_preview: bpy.props.BoolProperty(name="Preview", default=True)


def settings(context) -> XPlaneBulkEditSettings:
    return context.window_manager.xplane_bulk_edit


def scope_objects(context, scope: str) -> List[bpy.types.Object]:
    if scope == "SCENE":
        return list(context.scene.objects)
    selected = list(context.selected_objects)
    if scope == "SELECTED_CHILDREN":
        found = {o: None for o in selected}
        for obj in selected:
            for child in obj.children_recursive:
                found[child] = None
        return list(found)
    return selected


def current_pairs(s: XPlaneBulkEditSettings) -> List[Tuple[str, str]]:
    return [(p.find, p.replace) for p in s.pairs]


def plan_from_settings(context, objects=None) -> Tuple[List[Change], List[bpy.types.ID], str]:
    s = settings(context)
    if objects is None:
        objects = scope_objects(context, s.scope)
    try:
        changes, skipped = plan(objects, current_pairs(s), set(s.kinds), s.use_regex, s.match_case)
    except re.error as e:
        return [], [], f"Find is not a valid regular expression: {e}"
    return changes, skipped, ""


def _skipped_text(skipped: Sequence[bpy.types.ID]) -> str:
    if not skipped:
        return ""
    names = ", ".join(i.name for i in skipped[:3]) + ("..." if len(skipped) > 3 else "")
    return f"; left {len(skipped)} shared material(s)/light(s) alone, objects outside the selection use them too ({names})"


class XPLANE_OT_bulk_replace(bpy.types.Operator):
    """Replace text in the X-Plane settings (commands, datarefs, light levels, tooltips, custom attributes) of many objects"""

    bl_idname = "xplane.bulk_replace"
    bl_label = "Find And Replace"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        changes, skipped, problem = plan_from_settings(context)
        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}
        apply(changes)
        objects = len({c.field.obj for c in changes})
        self.report({"INFO"}, f"Changed {len(changes)} setting(s) on {objects} object(s)" + _skipped_text(skipped))
        return {"FINISHED"}


class XPLANE_OT_bulk_duplicate_replace(bpy.types.Operator):
    """Duplicate the selected objects and replace text in the X-Plane settings of the copies, then move them"""

    bl_idname = "xplane.bulk_duplicate_replace"
    bl_label = "Duplicate And Replace"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def execute(self, context):
        s = settings(context)
        originals = scope_objects(context, s.scope if s.scope != "SCENE" else "SELECTED")
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in originals:
            obj.select_set(True)
        if originals and context.view_layer.objects.active not in originals:
            context.view_layer.objects.active = originals[0]
        bpy.ops.object.duplicate(linked=False)
        copies = list(context.selected_objects)
        changes, skipped, problem = plan_from_settings(context, copies)
        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}
        apply(changes)
        self.report(
            {"INFO"},
            f"Duplicated {len(copies)} object(s) and changed {len(changes)} setting(s)" + _skipped_text(skipped),
        )
        return {"FINISHED"}

    def invoke(self, context, event):
        result = self.execute(context)
        if "FINISHED" in result:
            # Place the copies like Shift+D does
            bpy.ops.transform.translate("INVOKE_DEFAULT")
        return result


class XPLANE_OT_bulk_pair_add(bpy.types.Operator):
    """Add a find and replace pair"""

    bl_idname = "xplane.bulk_pair_add"
    bl_label = "Add Pair"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        settings(context).pairs.add()
        return {"FINISHED"}


class XPLANE_OT_bulk_pair_remove(bpy.types.Operator):
    """Remove this find and replace pair"""

    bl_idname = "xplane.bulk_pair_remove"
    bl_label = "Remove Pair"
    bl_options = {"INTERNAL"}

    index: bpy.props.IntProperty()

    def execute(self, context):
        pairs = settings(context).pairs
        if 0 <= self.index < len(pairs):
            pairs.remove(self.index)
        return {"FINISHED"}


class XPLANE_OT_bulk_pairs_swap(bpy.types.Operator):
    """Swap Find And Replace in every pair, to go back the other way (right to left instead of left to right)"""

    bl_idname = "xplane.bulk_pairs_swap"
    bl_label = "Swap Find And Replace"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        for pair in settings(context).pairs:
            pair.find, pair.replace = pair.replace, pair.find
        return {"FINISHED"}


PREVIEW_ROWS = 6


class XPLANE_PT_bulk_edit(Properties, bpy.types.Panel):
    bl_context = "scene"
    bl_label = "X-Plane Find And Replace"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        s = settings(context)
        layout = self.layout
        col = layout.column(align=True)
        for i, pair in enumerate(s.pairs):
            row = col.row(align=True)
            row.prop(pair, "find", text="")
            row.label(icon="FORWARD")
            row.prop(pair, "replace", text="")
            row.operator(XPLANE_OT_bulk_pair_remove.bl_idname, text="", icon="X").index = i
        row = col.row(align=True)
        row.operator(XPLANE_OT_bulk_pair_add.bl_idname, text="Add Pair", icon="ADD")
        row.operator(XPLANE_OT_bulk_pairs_swap.bl_idname, text="", icon="UV_SYNC_SELECT")

        layout.prop(s, "scope")
        grid = compact_grid(layout, columns=2, even_columns=True, align=True)
        for identifier, _, _ in KINDS:
            grid.prop_enum(s, "kinds", identifier)
        row = compact_row(layout)
        row.prop(s, "match_case", toggle=True)
        row.prop(s, "use_regex", text="Regex", toggle=True)

        changes, skipped, problem = plan_from_settings(context)
        box = layout.box()
        header = box.row()
        header.prop(
            s, "show_preview", text="", icon="TRIA_DOWN" if s.show_preview else "TRIA_RIGHT", emboss=False
        )
        if problem:
            header.label(text=problem, icon="ERROR")
        else:
            header.label(text=f"{len(changes)} change(s)")
        if s.show_preview:
            for change in changes[:PREVIEW_ROWS]:
                item = box.column(align=True)
                item.label(text=change.field.label)
                old = item.row()
                old.active = False
                old.label(text=change.old, icon="REMOVE")
                item.label(text=change.new, icon="ADD")
            if len(changes) > PREVIEW_ROWS:
                box.label(text=f"... and {len(changes) - PREVIEW_ROWS} more")
            if skipped:
                box.label(text=f"{len(skipped)} shared material(s)/light(s) left alone", icon="INFO")

        col = layout.column(align=True)
        col.scale_y = 1.2
        col.operator(XPLANE_OT_bulk_replace.bl_idname, icon="FILE_REFRESH")
        col.operator(XPLANE_OT_bulk_duplicate_replace.bl_idname, icon="DUPLICATE")


_classes = (
    XPlaneBulkEditPair,
    XPlaneBulkEditSettings,
    XPLANE_OT_bulk_replace,
    XPLANE_OT_bulk_duplicate_replace,
    XPLANE_OT_bulk_pair_add,
    XPLANE_OT_bulk_pair_remove,
    XPLANE_OT_bulk_pairs_swap,
    XPLANE_PT_bulk_edit,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.WindowManager.xplane_bulk_edit = bpy.props.PointerProperty(type=XPlaneBulkEditSettings)


def unregister():
    del bpy.types.WindowManager.xplane_bulk_edit
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
