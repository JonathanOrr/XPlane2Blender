"""
What an object is for X-Plane, in plain words, worked out from the settings it already has. The panels
(the ui package) draw from this; nothing here draws or stores anything of its own.

An object can be several things at once: a button that moves and glows is "Clickable", "Moves" and "Glows".
"""

import collections
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Union

import bpy

from io_xplane2blender import xplane_constants as C
from io_xplane2blender.xplane_helpers import get_action_fcurves, get_collections_in_scene

FileOwner = Union[bpy.types.Collection, bpy.types.Object]


# ---- Export files ----------------------------------------------------------------------------------------------
def is_file(owner: FileOwner) -> bool:
    if isinstance(owner, bpy.types.Collection):
        return owner.xplane.is_exportable_collection
    return owner.xplane.isExportableRoot


def export_files(scene: bpy.types.Scene) -> List[FileOwner]:
    """Every OBJ the scene exports, collections first, in outliner order"""
    found: List[FileOwner] = [c for c in get_collections_in_scene(scene)[1:] if is_file(c)]
    found.extend(o for o in scene.objects if o.xplane.isExportableRoot)
    return found


def file_objects(owner: FileOwner) -> List[bpy.types.Object]:
    if isinstance(owner, bpy.types.Collection):
        return list(owner.all_objects)
    return [owner, *owner.children_recursive]


def files_of(obj: bpy.types.Object, scene: bpy.types.Scene) -> List[FileOwner]:
    owners = [c for c in get_collections_in_scene(scene)[1:] if is_file(c) and obj.name in c.all_objects]
    parent = obj
    while parent is not None:
        if parent.xplane.isExportableRoot:
            owners.append(parent)
        parent = parent.parent
    return owners


def file_name(owner: FileOwner) -> str:
    return (owner.xplane.layer.name.strip() or owner.name) + ".obj"


def file_kind(owner: FileOwner) -> str:
    return "Cockpit" if owner.xplane.layer.export_type == C.EXPORT_TYPE_COCKPIT else "Aircraft part"


def _collections_inside_files(scene: bpy.types.Scene) -> List[bpy.types.Collection]:
    inside = []
    for owner in export_files(scene):
        if isinstance(owner, bpy.types.Collection):
            inside.append(owner)
            inside.extend(owner.children_recursive)
    return inside


def move_into_new_file(
    objects: Iterable[bpy.types.Object], name: str, scene: bpy.types.Scene, cockpit: Optional[bool] = None
) -> bpy.types.Collection:
    """
    A new export file holding the objects and their children. They leave the export files they were in, so nothing
    is exported twice; collections that only organize the scene keep them.
    """
    moving = []
    for obj in objects:
        for o in (obj, *obj.children_recursive):
            if o not in moving:
                moving.append(o)
    leaving = _collections_inside_files(scene)
    collection = bpy.data.collections.new(name)
    scene.collection.children.link(collection)
    for obj in moving:
        for old in leaving:
            if obj.name in old.objects:
                old.objects.unlink(obj)
        if obj.name not in collection.objects:
            collection.objects.link(obj)
        if obj.name in scene.collection.objects:
            scene.collection.objects.unlink(obj)
    collection.xplane.is_exportable_collection = True
    layer = collection.xplane.layer
    layer.name = name
    if cockpit is None:
        cockpit = any(o.type == "MESH" and o.xplane.manip.enabled for o in moving)
    layer.export_type = C.EXPORT_TYPE_COCKPIT if cockpit else C.EXPORT_TYPE_AIRCRAFT
    textures_from_materials(collection)
    return collection


# ---- Textures ---------------------------------------------------------------------------------------------------
# The detail texture preview's shader nodes, and where its last node remembers what fed the shader before it
PREVIEW_PREFIX = "XP2B Detail"
PREVIEW_FROM_NODE, PREVIEW_FROM_SOCKET = "xplane_from_node", "xplane_from_socket"


def preview_original(node) -> Optional["bpy.types.NodeSocket"]:
    """For the detail texture preview's last node: the socket that fed the shader before the preview, or None"""
    from_node = node.id_data.nodes.get(node.get(PREVIEW_FROM_NODE, ""))
    if from_node is None:
        return None
    return next((s for s in from_node.outputs if s.identifier == node.get(PREVIEW_FROM_SOCKET)), None)


def _image_from(socket) -> Optional[bpy.types.Image]:
    node = socket.node
    if node.name.startswith(PREVIEW_PREFIX):
        original = preview_original(node)
        return _image_from(original) if original is not None else None
    if node.type == "NORMAL_MAP":
        return _linked_image(node.inputs.get("Color"))
    if node.type == "TEX_IMAGE":
        return node.image
    return None


def _linked_image(node_input) -> Optional[bpy.types.Image]:
    """The image feeding a shader input, through a normal map node or the detail texture preview"""
    if node_input is None or not node_input.is_linked:
        return None
    return _image_from(node_input.links[0].from_socket)


def material_images(material: bpy.types.Material) -> Dict[str, bpy.types.Image]:
    """Day, night and normal images of a material set up like the importer does (Principled BSDF)"""
    found = {}
    if not material or not material.use_nodes or not material.node_tree:
        return found
    for node in material.node_tree.nodes:
        if node.type != "BSDF_PRINCIPLED":
            continue
        for key, input_names in (
            ("texture", ("Base Color",)),
            ("texture_lit", ("Emission Color", "Emission")),
            ("texture_normal", ("Normal",)),
        ):
            for input_name in input_names:
                image = _linked_image(node.inputs.get(input_name))
                if image is not None and key not in found:
                    found[key] = image
    return found


def textures_from_materials(owner: FileOwner) -> Dict[str, str]:
    """
    Fills the file's empty texture slots with the images its materials use most. An OBJ has one set of textures,
    so this is what X-Plane will draw every object of the file with. Returns what was filled
    """
    counts: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for obj in file_objects(owner):
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            for key, image in material_images(slot.material).items():
                if image.filepath:
                    counts[key][image.filepath] += 1
    layer = owner.xplane.layer
    filled = {}
    for key, counter in counts.items():
        if not getattr(layer, key):
            path = counter.most_common(1)[0][0]
            setattr(layer, key, path)
            filled[key] = path
    return filled


# ---- Clickable (manipulators) -----------------------------------------------------------------------------------
@dataclass(frozen=True)
class ControlKind:
    label: str
    group: str
    help: str
    cursor: str


GROUPS = ("Runs commands", "Sets a dataref", "Dragged", "Other")

# fmt: off
CONTROL_KINDS: Dict[str, ControlKind] = collections.OrderedDict((
    (C.MANIP_COMMAND,                     ControlKind("Button", "Runs commands", "Runs a command while it is held down", C.MANIP_CURSOR_BUTTON)),
    (C.MANIP_COMMAND_SWITCH_UP_DOWN2,     ControlKind("Switch, up / down", "Runs commands", "One command; X-Plane works out the direction from the animation", C.MANIP_CURSOR_UP_DOWN)),
    (C.MANIP_COMMAND_SWITCH_LEFT_RIGHT2,  ControlKind("Switch, left / right", "Runs commands", "One command; X-Plane works out the direction from the animation", C.MANIP_CURSOR_LEFT_RIGHT)),
    (C.MANIP_COMMAND_KNOB2,               ControlKind("Knob", "Runs commands", "One command; X-Plane works out the direction from the animation", C.MANIP_CURSOR_ROTATE_SMALL)),
    (C.MANIP_COMMAND_SWITCH_UP_DOWN,      ControlKind("Switch, up / down, two commands", "Runs commands", "Clicking the top half runs one command, the bottom half the other", C.MANIP_CURSOR_UP_DOWN)),
    (C.MANIP_COMMAND_SWITCH_LEFT_RIGHT,   ControlKind("Switch, left / right, two commands", "Runs commands", "Clicking the right half runs one command, the left half the other", C.MANIP_CURSOR_LEFT_RIGHT)),
    (C.MANIP_COMMAND_KNOB,                ControlKind("Knob, two commands", "Runs commands", "Clicking the right half or wheeling up runs one command, the left half the other", C.MANIP_CURSOR_ROTATE_SMALL)),
    (C.MANIP_COMMAND_AXIS,                ControlKind("Drag runs commands", "Runs commands", "Dragging along a direction runs one command, dragging back the other", C.MANIP_CURSOR_HAND)),
    (C.MANIP_TOGGLE,                      ControlKind("Toggle", "Sets a dataref", "Each click flips a dataref between two values", C.MANIP_CURSOR_BUTTON)),
    (C.MANIP_PUSH,                        ControlKind("Push", "Sets a dataref", "Sets a dataref while held down, another value when released", C.MANIP_CURSOR_BUTTON)),
    (C.MANIP_RADIO,                       ControlKind("Radio button", "Sets a dataref", "Sets a dataref to one value when clicked", C.MANIP_CURSOR_BUTTON)),
    (C.MANIP_DELTA,                       ControlKind("Step", "Sets a dataref", "Adds to a dataref on click and while held, between a lowest and highest value", C.MANIP_CURSOR_BUTTON)),
    (C.MANIP_WRAP,                        ControlKind("Step and wrap around", "Sets a dataref", "Like Step, but goes back to the start after the highest value", C.MANIP_CURSOR_BUTTON)),
    (C.MANIP_AXIS_KNOB,                   ControlKind("Knob", "Sets a dataref", "Clicking the right or left half steps a dataref up or down", C.MANIP_CURSOR_ROTATE_SMALL)),
    (C.MANIP_AXIS_SWITCH_UP_DOWN,         ControlKind("Switch, up / down", "Sets a dataref", "Clicking the top or bottom half steps a dataref up or down", C.MANIP_CURSOR_UP_DOWN)),
    (C.MANIP_AXIS_SWITCH_LEFT_RIGHT,      ControlKind("Switch, left / right", "Sets a dataref", "Clicking the right or left half steps a dataref up or down", C.MANIP_CURSOR_LEFT_RIGHT)),
    (C.MANIP_DRAG_ROTATE,                 ControlKind("Turn by dragging", "Dragged", "Dragging turns it the way it is animated; the dataref comes from the animation", C.MANIP_CURSOR_ROTATE_MEDIUM)),
    (C.MANIP_DRAG_ROTATE_DETENT,          ControlKind("Turn by dragging, with detents", "Dragged", "Like Turn by dragging, with ranges it stops in", C.MANIP_CURSOR_ROTATE_MEDIUM)),
    (C.MANIP_DRAG_AXIS,                   ControlKind("Slide by dragging", "Dragged", "Dragging along a direction moves a dataref between two values", C.MANIP_CURSOR_HAND)),
    (C.MANIP_DRAG_AXIS_DETENT,            ControlKind("Slide by dragging, with detents", "Dragged", "Like Slide by dragging, with ranges it stops in (levers with gates)", C.MANIP_CURSOR_HAND)),
    (C.MANIP_DRAG_XY,                     ControlKind("Drag in two directions", "Dragged", "Dragging left/right and up/down sets two datarefs (yokes, sticks)", C.MANIP_CURSOR_FOUR_ARROWS)),
    (C.MANIP_DRAG_AXIS_PIX,               ControlKind("Drag the mouse sideways", "Dragged", "Dragging the mouse left and right changes a dataref, however the object is turned", C.MANIP_CURSOR_LEFT_RIGHT)),
    (C.MANIP_NOOP,                        ControlKind("Blocks clicks", "Other", "Does nothing, and stops clicks reaching what is behind it", C.MANIP_CURSOR_ARROW)),
))
# fmt: on

_AUTODETECT_IMPLICIT = {C.MANIP_DRAG_AXIS_DETENT, C.MANIP_DRAG_ROTATE, C.MANIP_DRAG_ROTATE_DETENT}
_TWO_COMMANDS = {
    C.MANIP_COMMAND_SWITCH_UP_DOWN: ("Up command", "Down command"),
    C.MANIP_COMMAND_SWITCH_LEFT_RIGHT: ("Right command", "Left command"),
    C.MANIP_COMMAND_KNOB: ("Clockwise command", "Counter-clockwise command"),
    C.MANIP_COMMAND_AXIS: ("Forward command", "Back command"),
}
_ONE_COMMAND = {C.MANIP_COMMAND, C.MANIP_COMMAND_KNOB2, C.MANIP_COMMAND_SWITCH_UP_DOWN2, C.MANIP_COMMAND_SWITCH_LEFT_RIGHT2}
_STEPPED = {C.MANIP_AXIS_KNOB, C.MANIP_AXIS_SWITCH_UP_DOWN, C.MANIP_AXIS_SWITCH_LEFT_RIGHT}
_DETENTS = {C.MANIP_DRAG_AXIS_DETENT, C.MANIP_DRAG_ROTATE_DETENT}


def control_kind(manip) -> ControlKind:
    return CONTROL_KINDS.get(manip.type, ControlKind(manip.type, "Other", "", C.MANIP_CURSOR_HAND))


@dataclass(frozen=True)
class Field:
    prop: str
    label: str
    kind: str = "value"  # "value", "dataref", "command" or "bool"


def manip_fields(manip) -> List[Field]:
    """The settings the manipulator's kind uses, in the order a person fills them in"""
    t = manip.type
    fields: List[Field] = []
    if t in _ONE_COMMAND:
        fields.append(Field("command", "Command", "command"))
    if t in _TWO_COMMANDS:
        plus, minus = _TWO_COMMANDS[t]
        fields += [Field("positive_command", plus, "command"), Field("negative_command", minus, "command")]
    if t in _TWO_COMMANDS or t in _ONE_COMMAND or t == C.MANIP_NOOP:
        if t == C.MANIP_COMMAND_AXIS:
            fields += [Field("dx", "Drag X"), Field("dy", "Drag Y"), Field("dz", "Drag Z")]
        return fields

    from_animation = False
    if t in _AUTODETECT_IMPLICIT:
        fields.append(Field("autodetect_datarefs", "Datarefs from the animation", "bool"))
        from_animation = manip.autodetect_datarefs
    elif t == C.MANIP_DRAG_AXIS:
        fields.append(Field("autodetect_settings_opt_in", "Direction and values from the animation", "bool"))
        if manip.autodetect_settings_opt_in:
            fields.append(Field("autodetect_datarefs", "Datarefs from the animation", "bool"))
            from_animation = manip.autodetect_datarefs

    if not from_animation:
        if t == C.MANIP_DRAG_XY:
            fields += [Field("dataref1", "Left / right dataref", "dataref"), Field("dataref2", "Up / down dataref", "dataref")]
        elif t in _DETENTS:
            fields += [Field("dataref1", "Dataref", "dataref"), Field("dataref2", "Detent dataref", "dataref")]
        else:
            fields.append(Field("dataref1", "Dataref", "dataref"))

    if t == C.MANIP_TOGGLE:
        fields += [Field("v_on", "On value"), Field("v_off", "Off value")]
    elif t == C.MANIP_PUSH:
        fields += [Field("v_down", "Value while held"), Field("v_up", "Value when released")]
    elif t == C.MANIP_RADIO:
        fields.append(Field("v_down", "Value when clicked"))
    elif t in (C.MANIP_DELTA, C.MANIP_WRAP):
        fields += [
            Field("v_down", "Add on click"),
            Field("v_hold", "Add while held"),
            Field("v1_min", "Lowest"),
            Field("v1_max", "Highest"),
        ]
    elif t in _STEPPED:
        fields += [
            Field("v1", "Lowest"),
            Field("v2", "Highest"),
            Field("click_step", "Step per click"),
            Field("hold_step", "Step while held"),
        ]
    elif t == C.MANIP_DRAG_XY:
        fields += [
            Field("dx", "Drag width"),
            Field("dy", "Drag height"),
            Field("v1_min", "Left / right from"),
            Field("v1_max", "Left / right to"),
            Field("v2_min", "Up / down from"),
            Field("v2_max", "Up / down to"),
        ]
    elif t == C.MANIP_DRAG_AXIS and not manip.autodetect_settings_opt_in:
        fields += [
            Field("dx", "Drag X"),
            Field("dy", "Drag Y"),
            Field("dz", "Drag Z"),
            Field("v1", "Value at start"),
            Field("v2", "Value at end"),
        ]
    elif t == C.MANIP_DRAG_AXIS_PIX:
        fields += [
            Field("dx", "Drag distance (pixels)"),
            Field("step", "Step"),
            Field("exp", "Speed curve"),
            Field("v1", "Lowest"),
            Field("v2", "Highest"),
        ]
    if t in C.MANIPULATORS_MOUSE_WHEEL:
        fields.append(Field("wheel_delta", "Mouse wheel step"))
    return fields


def has_detent_ranges(manip) -> bool:
    return manip.type in _DETENTS


# ---- Animation ---------------------------------------------------------------------------------------------------
def motion_datarefs(obj) -> List[Tuple[int, "bpy.types.PropertyGroup"]]:
    return [(i, d) for i, d in enumerate(obj.xplane.datarefs) if d.anim_type == C.ANIM_TYPE_TRANSFORM]


def visibility_datarefs(obj) -> List[Tuple[int, "bpy.types.PropertyGroup"]]:
    return [(i, d) for i, d in enumerate(obj.xplane.datarefs) if d.anim_type in (C.ANIM_TYPE_SHOW, C.ANIM_TYPE_HIDE)]


def dataref_keys(id_data: bpy.types.ID, index: int, bone: Optional[bpy.types.Bone] = None) -> List[Tuple[float, float]]:
    """(frame, dataref value) of each key of xplane.datarefs[index] of an object, or of a bone of armature data"""
    path = f'bones["{bone.name}"].xplane.datarefs[{index}].value' if bone else f"xplane.datarefs[{index}].value"
    for fcurve in get_action_fcurves(id_data):
        if fcurve.data_path == path:
            return [(k.co[0], k.co[1]) for k in fcurve.keyframe_points]
    return []


# ---- Summary and checks ------------------------------------------------------------------------------------------
def summary(obj: bpy.types.Object) -> List[str]:
    """Short words for what the object is, e.g. ["Button", "Moves", "Glows"]"""
    words = []
    x = obj.xplane
    if obj.type == "LIGHT":
        words.append("Light")
    elif obj.type == "EMPTY" and x.special_empty_props.special_type != C.EMPTY_USAGE_NONE:
        words.append(
            {
                C.EMPTY_USAGE_WHEEL: "Wheel",
                C.EMPTY_USAGE_MAGNET: "Tablet mount",
                C.EMPTY_USAGE_EMITTER_PARTICLE: "Particle emitter",
            }.get(x.special_empty_props.special_type, "Attachment")
        )
    if obj.type == "MESH" and x.manip.enabled:
        words.append(control_kind(x.manip).label)
    if motion_datarefs(obj):
        words.append("Moves")
    if visibility_datarefs(obj):
        words.append("Shows / hides")
    if x.lightLevel:
        words.append("Glows")
    if obj.type == "MESH":
        material = obj.active_material
        if material is not None:
            if material.xplane.cockpit_feature == C.COCKPIT_FEATURE_PANEL:
                words.append("2D panel screen")
            elif material.xplane.cockpit_feature == C.COCKPIT_FEATURE_DEVICE:
                words.append("Avionics screen")
            if not material.xplane.draw:
                words.append("Invisible")
        if x.hud_glass:
            words.append("HUD glass")
    if not words:
        words.append("Part" if obj.type == "MESH" else obj.type.capitalize())
    return words


def problems(obj: bpy.types.Object, scene: bpy.types.Scene, check_file: bool = True) -> List[str]:
    """Unfinished work on the object. None of it stops an export: what is missing is left out"""
    found = []
    x = obj.xplane
    if check_file and obj.type in ("MESH", "LIGHT", "EMPTY", "ARMATURE") and not files_of(obj, scene):
        found.append("Not in an export file, so it is not exported")
    if obj.type == "MESH":
        if x.manip.enabled:
            for field in manip_fields(x.manip):
                if field.kind in ("command", "dataref") and not getattr(x.manip, field.prop).strip():
                    found.append(f"Clickable: no {field.label.lower()} yet")
        if not any(slot.material for slot in obj.material_slots):
            found.append("No material: exported with the default look")
        for slot in obj.material_slots:
            m = slot.material
            if m and m.xplane.cockpit_feature == C.COCKPIT_FEATURE_DEVICE:
                if not any(getattr(m.xplane, f"device_bus_{bus}") for bus in range(6)):
                    found.append(f"Screen '{m.name}': no power bus chosen")
            if m and m.xplane.lightLevel and not m.xplane.lightLevel_dataref.strip():
                found.append(f"Glow of material '{m.name}': no dataref yet, left out")
    if x.lightLevel and not x.lightLevel_dataref.strip():
        found.append("Glow: no dataref yet, left out")
    for i, d in enumerate(x.datarefs):
        if not d.path.strip():
            found.append("Animation: a dataref has no name")
        elif d.anim_type == C.ANIM_TYPE_TRANSFORM and len(dataref_keys(obj, i)) < 2:
            found.append(f"Moves: '{d.path}' needs keys at two values or more")
    if obj.type == "LIGHT":
        light = obj.data.xplane
        if light.type in (C.LIGHT_AUTOMATIC, C.LIGHT_NAMED, C.LIGHT_PARAM) and not light.name.strip():
            found.append("Light: no X-Plane light chosen yet")
    return found


# ---- Copying settings ---------------------------------------------------------------------------------------------
def copy_group(source, target) -> None:
    """Copies every stored setting of a property group, nested groups and lists included"""
    for prop in source.bl_rna.properties:
        key = prop.identifier
        if key == "rna_type":
            continue
        if prop.type == "POINTER":
            copy_group(getattr(source, key), getattr(target, key))
        elif prop.type == "COLLECTION":
            items = getattr(target, key)
            items.clear()
            for item in getattr(source, key):
                copy_group(item, items.add())
        elif not prop.is_readonly:
            setattr(target, key, getattr(source, key))


GLOW_SETTINGS = (
    "lightLevel",
    "lightLevel_v1",
    "lightLevel_v2",
    "lightLevel_dataref",
    "lightLevel_photometric",
    "lightLevel_brightness",
)


def copy_settings(what: str, source: bpy.types.Object, target: bpy.types.Object) -> bool:
    """Copies one kind of X-Plane settings between objects. Returns False when the target cannot take them"""
    if what == "CLICK":
        if target.type != "MESH":
            return False
        copy_group(source.xplane.manip, target.xplane.manip)
    elif what == "GLOW":
        for key in GLOW_SETTINGS:
            setattr(target.xplane, key, getattr(source.xplane, key))
    elif what == "VISIBILITY":
        for _, d in visibility_datarefs(source):
            copy_group(d, target.xplane.datarefs.add())
    elif what == "LIGHT":
        if target.type != "LIGHT" or target.data == source.data:
            return target.type == "LIGHT"
        copy_group(source.data.xplane, target.data.xplane)
    elif what == "ATTACHMENT":
        if target.type != "EMPTY":
            return False
        copy_group(source.xplane.special_empty_props, target.xplane.special_empty_props)
    else:
        raise ValueError(what)
    return True


def unfinished_in_files(scene: bpy.types.Scene) -> List[Tuple[str, str]]:
    """(object name, problem) for every object of every export file"""
    seen = set()
    found = []
    for owner in export_files(scene):
        for obj in file_objects(owner):
            if obj.name in seen:
                continue
            seen.add(obj.name)
            found.extend((obj.name, problem) for problem in problems(obj, scene, check_file=False))
    return found
