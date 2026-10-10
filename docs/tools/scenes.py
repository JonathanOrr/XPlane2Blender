"""
The demo cockpit the screenshots are taken of, built from nothing so that every run is the same: a panel with a
heading knob, a landing light button and a switch, a screen, a flood light, a dome light, a VR tablet mount, a light
nobody has picked a kind for yet, and a coffee cup that is in no export file.
"""

import bpy

from io_xplane2blender import xplane_constants as C


def _clear() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.armatures,
    ):
        for item in list(block):
            block.remove(item)


def _file(name: str, kind: str) -> bpy.types.Collection:
    coll = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(coll)
    coll.xplane.is_exportable_collection = True
    coll.xplane.layer.name = name
    coll.xplane.layer.export_type = kind
    return coll


def _box(name: str, size, location, coll: bpy.types.Collection) -> bpy.types.Object:
    """A box of size (x, y, z) in meters, its origin in its middle"""
    mesh = bpy.data.meshes.new(name)
    x, y, z = (s / 2 for s in size)
    corners = [
        (-x, -y, -z),
        (x, -y, -z),
        (x, y, -z),
        (-x, y, -z),
        (-x, -y, z),
        (x, -y, z),
        (x, y, z),
        (-x, y, z),
    ]
    faces = [
        (0, 3, 2, 1),
        (4, 5, 6, 7),
        (0, 1, 5, 4),
        (1, 2, 6, 5),
        (2, 3, 7, 6),
        (3, 0, 4, 7),
    ]
    mesh.from_pydata(corners, [], faces)
    mesh.uv_layers.new(name="UVMap")
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    coll.objects.link(obj)
    return obj


def _material(name: str) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (0.18, 0.19, 0.2, 1.0)
    return mat


def _select(*objs: bpy.types.Object) -> None:
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0] if objs else None


def _reset(group) -> None:
    """Back to its defaults: the panels keep their state on the window manager, which outlives a scene"""
    for prop in group.bl_rna.properties:
        if (
            prop.identifier == "rna_type"
            or prop.is_readonly
            and prop.type != "COLLECTION"
        ):
            continue
        if prop.type == "COLLECTION":
            getattr(group, prop.identifier).clear()
        else:
            group.property_unset(prop.identifier)


def build() -> None:
    _clear()
    wm = bpy.context.window_manager
    for name in ("xplane_panels", "xplane_bulk_edit"):
        if hasattr(wm, name):
            _reset(getattr(wm, name))
    scene = bpy.context.scene
    scene.frame_set(1)
    cockpit = _file("cockpit", C.EXPORT_TYPE_COCKPIT)
    _file("exterior", C.EXPORT_TYPE_AIRCRAFT)
    paint = _material("cockpit paint")

    panel = _box("glareshield panel", (0.6, 0.02, 0.12), (0, 0.6, 1.0), cockpit)
    panel.data.materials.append(paint)

    knob = _box("heading knob", (0.03, 0.03, 0.03), (0.12, 0.575, 1.02), cockpit)
    knob.data.materials.append(paint)
    knob.xplane.manip.enabled = True
    knob.xplane.manip.type = C.MANIP_COMMAND_KNOB
    knob.xplane.manip.positive_command = "sim/autopilot/heading_up"
    knob.xplane.manip.negative_command = "sim/autopilot/heading_down"
    knob.xplane.manip.tooltip = "Heading"
    _select(knob)
    bpy.ops.xplane.anim_range(
        dataref="sim/cockpit/autopilot/heading_mag",
        value_from=0,
        value_to=360,
        axis="Y",
        offset_from=0,
        offset_to=-360,
    )

    button = _box(
        "landing light button", (0.025, 0.02, 0.025), (-0.12, 0.58, 1.02), cockpit
    )
    button.data.materials.append(paint)
    _select(button)
    bpy.ops.xplane.anim_push_button(
        command="sim/lights/landing_lights_toggle", axis="Y", distance=2.0
    )
    button.xplane.manip.tooltip = "Landing lights"

    pedestal = _box("center pedestal", (0.2, 0.3, 0.08), (0, 0.35, 0.8), cockpit)
    pedestal.data.materials.append(paint)
    throttle = _box("throttle lever", (0.02, 0.02, 0.12), (0, 0.35, 0.84), cockpit)
    throttle.data.transform(
        __import__("mathutils").Matrix.Translation((0, 0, 0.06))
    )  # Its origin is its pivot
    throttle.data.materials.append(paint)
    _select(throttle)
    bpy.ops.xplane.anim_range(
        dataref="sim/cockpit2/engine/actuators/throttle_ratio_all",
        value_from=0,
        value_to=1,
        axis="X",
        offset_from=-20,
        offset_to=20,
    )

    screen = _box(
        "primary flight display", (0.16, 0.004, 0.16), (-0.25, 0.59, 0.85), cockpit
    )
    display = _material("pfd screen")
    display.xplane.cockpit_feature = C.COCKPIT_FEATURE_DEVICE
    display.xplane.device_name = C.DEVICE_G1000_PFD1
    display.xplane.device_bus_0 = True
    screen.data.materials.append(display)

    flood = bpy.data.lights.new("flood light", "SPOT")
    flood.xplane.type = C.LIGHT_SPILL_CUSTOM
    flood.xplane.size = 0.6
    flood.xplane.spill_dim = 0.8
    flood.xplane.dataref = "sim/cockpit2/switches/panel_brightness_ratio[0]"
    flood_obj = bpy.data.objects.new("flood light", flood)
    flood_obj.location = (0, 0.3, 1.3)
    cockpit.objects.link(flood_obj)

    dome = bpy.data.lights.new("dome light", "POINT")
    dome.xplane.type = C.LIGHT_NAMED
    dome.xplane.name = "airplane_generic_core"
    dome_obj = bpy.data.objects.new("dome light", dome)
    dome_obj.location = (0, 0, 1.6)
    cockpit.objects.link(dome_obj)

    unfinished = bpy.data.objects.new(
        "reading light", bpy.data.lights.new("reading light", "SPOT")
    )
    unfinished.data.xplane.type = C.LIGHT_NAMED
    unfinished.location = (0.4, 0.2, 1.4)
    cockpit.objects.link(unfinished)

    tablet = bpy.data.objects.new("tablet mount", None)
    tablet.empty_display_type = "ARROWS"
    tablet.empty_display_size = 0.05
    tablet.location = (0.45, 0.4, 0.9)
    tablet.xplane.special_empty_props.special_type = C.EMPTY_USAGE_MAGNET
    tablet.xplane.special_empty_props.magnet_props.debug_name = "Pilot tablet"
    tablet.xplane.special_empty_props.magnet_props.magnet_type_is_xpad = True
    cockpit.objects.link(tablet)

    armature = bpy.data.armatures.new("seat")
    rig = bpy.data.objects.new("seat rig", armature)
    rig.location = (0.4, -0.2, 0.4)
    cockpit.objects.link(rig)
    _select(rig)
    bpy.ops.object.mode_set(mode="EDIT")
    bone = armature.edit_bones.new("seat slide")
    bone.head, bone.tail = (0, 0, 0), (0, 0.1, 0)
    bpy.ops.object.mode_set(mode="OBJECT")

    cup = _box("coffee cup", (0.08, 0.08, 0.1), (0.5, 0.0, 0.8), scene.collection)
    cup.data.materials.append(_material("cup"))

    _select(panel)


def select(name: str) -> bpy.types.Object:
    obj = bpy.data.objects[name]
    _select(obj)
    return obj


# ---- Extra steps of some shots, after the scene is built and the object selected


def checked() -> None:
    """The Unfinished Work panel after Check"""
    bpy.ops.xplane.check()


def find_and_replace() -> None:
    """A copy of the captain's side for the first officer"""
    settings = bpy.context.window_manager.xplane_bulk_edit
    pair = settings.pairs.add()
    pair.find, pair.replace = "heading", "course"
    pair = settings.pairs.add()
    pair.find, pair.replace = "Heading", "Course"


def overlays_on() -> None:
    """The X-Plane overlays of the 3D view, all on, labels for every click zone"""
    view = bpy.data.screens["Layout"].xplane_view
    view.show_click_zones = True
    view.click_labels = "ALL"
    view.show_motion = True
    view.show_lever = True
    view.show_lights = False


def cards() -> None:
    """The landing light button with a glow and a show / hide, as a backlit button on a powered bus"""
    from io_xplane2blender import xplane_constants as C

    button = bpy.data.objects["landing light button"]
    button.xplane.lightLevel = True
    button.xplane.lightLevel_dataref = (
        "sim/cockpit2/switches/instrument_brightness_ratio[0]"
    )
    shown = button.xplane.datarefs.add()
    shown.path = "sim/cockpit2/electrical/bus_volts[0]"
    shown.anim_type = C.ANIM_TYPE_SHOW
    shown.show_hide_v1 = 20
    shown.show_hide_v2 = 30
