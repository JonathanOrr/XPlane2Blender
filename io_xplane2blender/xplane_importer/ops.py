"""Operators and menu entries for importing X-Plane objects and aircraft"""

import os
from typing import List, Sequence

import bpy
from bpy_extras.io_utils import ImportHelper

from io_xplane2blender.viewport.settings import view_settings

from . import frames
from .acf_parser import AcfParseError, parse_acf_file
from .aircraft import import_aircraft
from .common import ImportOptions, ImportReport
from .importing import import_obj_file


def _option_properties():
    """The option properties shared by the OBJ and ACF importers"""
    return {
        "import_materials": bpy.props.BoolProperty(
            name="Textures and Materials",
            description="Load the texture images and build shader nodes so it looks like it does in X-Plane",
            default=True,
        ),
        "import_animations": bpy.props.BoolProperty(
            name="Animations",
            description="Create the dataref animations and show/hide settings (keyframes on Empties)",
            default=True,
        ),
        "import_manipulators": bpy.props.BoolProperty(
            name="Manipulators",
            description="Set up the clickable manipulators on the meshes that have them",
            default=True,
        ),
        "import_lights": bpy.props.BoolProperty(
            name="Lights",
            description="Create X-Plane lights as Blender lights",
            default=True,
        ),
        "hide_default_hidden": bpy.props.BoolProperty(
            name="Mark What X-Plane Hides",
            description="Draw a sphere around the show/hide parts that X-Plane would not draw with the datarefs at their "
            "default values, and leave them out of renders. They stay visible and are exported like any part",
            default=True,
        ),
        "all_lods": bpy.props.BoolProperty(
            name="All LODs",
            description="Import every level of detail instead of only the first",
            default=False,
        ),
        "make_exportable": bpy.props.BoolProperty(
            name="Make Export Files",
            description="Tick each imported OBJ's collection as an export file, so Export writes them again. "
            "Their texture and export settings are filled in either way, you can tick a single collection later",
            default=False,
        ),
        "lit_strength": bpy.props.FloatProperty(
            name="Night Light Strength",
            description="How bright the _LIT texture glows. 0 shows the daytime look",
            default=0.0,
            min=0.0,
            soft_max=10.0,
        ),
        "light_strength": bpy.props.FloatProperty(
            name="Light Strength",
            description="Switches the spill lights on, such as the cockpit annunciator and panel lights. "
            "They are dataref driven in X-Plane and off in the parked pose, so 0 keeps them from lighting the scene. "
            "1 is the brightness the light's parameters ask for",
            default=0.0,
            min=0.0,
            soft_max=10.0,
        ),
        "show_result": bpy.props.BoolProperty(
            name="Show In Viewport",
            description="Switch the 3D viewport to the textured Material Preview, hide the dashed parent lines and frame"
            " everything. With many lights, Blender's own light gizmos are hidden (Overlays > Extras) and the X-Plane"
            " overlay marks the lights instead",
            default=True,
        ),
        "scale": bpy.props.FloatProperty(
            name="Scale",
            description="Multiplies all sizes. X-Plane uses meters, like Blender's default",
            default=1.0,
            min=0.0001,
        ),
    }


def _options_from(op) -> ImportOptions:
    keys = (
        "import_materials",
        "import_animations",
        "import_manipulators",
        "import_lights",
        "all_lods",
        "hide_default_hidden",
        "make_exportable",
        "lit_strength",
        "light_strength",
        "scale",
    )
    options = ImportOptions(**{k: getattr(op, k) for k in keys if hasattr(op, k)})
    options.include_not_drawn = getattr(op, "include_not_drawn", False)
    return options


_last_report_lines = []

# From this many lights, Blender's own drawing of lights (a ground line and a circle of fixed size each) is hidden
CROWDED_LIGHTS = 20


def _is_crowded(report: ImportReport) -> bool:
    return report.lights_imported >= CROWDED_LIGHTS


def _frame_everything(context, crowded: bool = False) -> None:
    """
    Switch every 3D viewport to the textured preview and frame what was imported. With many lights, Blender's own
    gizmos (Overlays > Extras) are hidden, which keeps the lights lighting, and the X-Plane overlay marks them instead
    """
    if crowded and context.screen is not None:
        view = view_settings(context)
        if view is not None:
            view.show_lights = True
    for area in context.screen.areas if context.screen else []:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.shading.type = "MATERIAL"
                space.clip_end = max(space.clip_end, 5000.0)
                # Every animated part hangs on an empty, and each would get a dashed line to its parent
                space.overlay.show_relationship_lines = False
                if crowded:
                    space.overlay.show_extras = False
        region = next((r for r in area.regions if r.type == "WINDOW"), None)
        if region is not None:
            try:
                with context.temp_override(area=area, region=region):
                    bpy.ops.view3d.view_all(center=False)
            except (RuntimeError, AttributeError):
                pass


class IMPORT_OT_xplane_report(bpy.types.Operator):
    """What an import did, and what it could not do"""

    bl_idname = "import_scene.xplane_report"
    bl_label = "X-Plane Import Finished"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=520)

    def draw(self, context):
        layout = self.layout
        for index, (icon, text) in enumerate(_last_report_lines):
            row = layout.row()
            row.label(text=text, icon=icon if index == 0 or icon != "INFO" else "NONE")


def _crowded_notes(report: ImportReport, crowded: bool) -> List[str]:
    if not crowded:
        return []
    return [
        f"{report.lights_imported} lights: shown as rings, Blender's gizmos off (Overlays > Extras)"
    ]


def _show_popup(report: ImportReport, notes: Sequence[str] = ()) -> None:
    if bpy.app.background:
        return
    lines = [("CHECKMARK" if not report.errors else "ERROR", report.summary())]
    lines += [("INFO", note) for note in notes]
    lines += [("ERROR", e[:110]) for e in report.errors[:6]]
    lines += [("ERROR", w[:110]) for w in report.warnings[:8]]
    extra = len(report.warnings) - 8
    if extra > 0:
        lines.append(("INFO", f"...and {extra} more, see the System Console"))
    _last_report_lines[:] = lines
    bpy.ops.import_scene.xplane_report("INVOKE_DEFAULT")


def _show_report(operator, report: ImportReport, notes: Sequence[str] = ()) -> None:
    operator.report({"INFO"}, report.summary())
    for note in notes:
        operator.report({"INFO"}, note)
    for warning in report.warnings[:8]:
        operator.report({"WARNING"}, warning)
    for error in report.errors[:8]:
        operator.report({"ERROR"}, error)
    if len(report.warnings) > 8:
        operator.report(
            {"WARNING"},
            f"...and {len(report.warnings) - 8} more warnings, see the System Console",
        )
    for line in report.warnings + report.errors:
        print("X-Plane import:", line)
    _show_popup(report, notes)


class IMPORT_OT_xplane_obj(bpy.types.Operator, ImportHelper):
    """Import X-Plane objects (.obj), with their textures, animations and manipulators"""

    bl_idname = "import_scene.xplane_obj"
    bl_label = "Import X-Plane Object"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    filename_ext = ".obj"
    filter_glob: bpy.props.StringProperty(default="*.obj", options={"HIDDEN"})
    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"}
    )
    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    __annotations__.update(_option_properties())

    def execute(self, context):
        report = ImportReport()
        options = _options_from(self)
        paths = [os.path.join(self.directory, f.name) for f in self.files] or [
            self.filepath
        ]
        wm = context.window_manager
        wm.progress_begin(0, max(1, len(paths)))
        imported = []
        for number, path in enumerate(paths):
            wm.progress_update(number)
            built = import_obj_file(
                path, options, report, update_view_layer=False, settle_frames=False
            )
            if built is not None:
                imported.extend(built.objects)
        frames.settle(imported, context.scene)
        wm.progress_end()
        context.view_layer.update()
        crowded = _is_crowded(report) and self.show_result
        _show_report(self, report, _crowded_notes(report, crowded))
        if report.files_imported and self.show_result:
            _frame_everything(context, crowded)
        return {"FINISHED"} if report.files_imported else {"CANCELLED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        box = layout.box()
        box.label(text="Bring in", icon="IMPORT")
        for name in (
            "import_materials",
            "import_animations",
            "import_manipulators",
            "import_lights",
            "all_lods",
            "hide_default_hidden",
        ):
            box.prop(self, name)
        box = layout.box()
        box.label(text="Setup", icon="PREFERENCES")
        box.prop(self, "make_exportable")
        box.prop(self, "lit_strength")
        box.prop(self, "light_strength")
        box.prop(self, "scale")
        box.prop(self, "show_result")


_livery_items_cache = {}


def _livery_items(self, context):
    """Dropdown entries for the liveries of the aircraft that is selected in the file browser"""
    items = [("DEFAULT", "Default textures", "Use the textures the objects ask for")]
    path = bpy.path.abspath(self.filepath) if self.filepath else ""
    if path.lower().endswith(".acf") and os.path.isfile(path):
        folder = os.path.join(os.path.dirname(path), "liveries")
        try:
            names = sorted(
                e for e in os.listdir(folder) if os.path.isdir(os.path.join(folder, e))
            )
        except OSError:
            names = []
        items += [(n, n, f"Textures from the {n} livery") for n in names]
    # Blender needs the strings to stay alive
    _livery_items_cache["items"] = items
    return items


class IMPORT_OT_xplane_aircraft(bpy.types.Operator, ImportHelper):
    """Import a whole X-Plane aircraft from its .acf file: every object, with textures, animations and manipulators"""

    bl_idname = "import_scene.xplane_aircraft"
    bl_label = "Import X-Plane Aircraft"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    filename_ext = ".acf"
    filter_glob: bpy.props.StringProperty(default="*.acf", options={"HIDDEN"})

    livery: bpy.props.EnumProperty(
        name="Livery", description="Which set of textures to use", items=_livery_items
    )
    include_damage: bpy.props.BoolProperty(
        name="Damage Objects",
        description="Also import the objects that only show when a part breaks",
        default=False,
    )
    include_not_drawn: bpy.props.BoolProperty(
        name="Not Drawn Objects",
        description="Also show the objects the aircraft file flags as drawn nowhere, for example placeholders and easter eggs",
        default=False,
    )
    include_attached: bpy.props.BoolProperty(
        name="Part Attached Objects",
        description="Also import objects attached to wings, gear or the body. They are placed at the aircraft origin",
        default=False,
    )

    __annotations__.update(_option_properties())

    def execute(self, context):
        report = ImportReport()
        options = _options_from(self)
        livery = "" if self.livery == "DEFAULT" else self.livery
        wm = context.window_manager
        wm.progress_begin(0, 100)

        def progress(number: int, total: int) -> None:
            wm.progress_update(int(100 * number / max(total, 1)))

        root = import_aircraft(
            bpy.path.abspath(self.filepath),
            options,
            report,
            livery=livery,
            include_damage=self.include_damage,
            include_attached=self.include_attached,
            progress=progress,
        )
        wm.progress_end()
        crowded = _is_crowded(report) and self.show_result
        _show_report(self, report, _crowded_notes(report, crowded))
        done = root is not None and report.files_imported
        if done and self.show_result:
            _frame_everything(context, crowded)
        return {"FINISHED"} if done else {"CANCELLED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        box = layout.box()
        box.label(text="Aircraft", icon="OBJECT_DATA")
        box.prop(self, "livery")
        box.prop(self, "include_damage")
        box.prop(self, "include_attached")
        box.prop(self, "include_not_drawn")
        box = layout.box()
        box.label(text="Bring in", icon="IMPORT")
        for name in (
            "import_materials",
            "import_animations",
            "import_manipulators",
            "import_lights",
            "all_lods",
            "hide_default_hidden",
        ):
            box.prop(self, name)
        box = layout.box()
        box.label(text="Setup", icon="PREFERENCES")
        box.prop(self, "make_exportable")
        box.prop(self, "lit_strength")
        box.prop(self, "light_strength")
        box.prop(self, "scale")
        box.prop(self, "show_result")


_classes = (IMPORT_OT_xplane_obj, IMPORT_OT_xplane_aircraft, IMPORT_OT_xplane_report)
# Drag and drop handlers only exist in Blender 4.1 and later
if hasattr(bpy.types, "FileHandler"):

    class IO_FH_xplane_aircraft(bpy.types.FileHandler):
        """Drop an .acf onto the 3D viewport to import the aircraft (Blender 4.1 and later)"""

        bl_idname = "IO_FH_xplane_aircraft"
        bl_label = "X-Plane Aircraft"
        bl_import_operator = "import_scene.xplane_aircraft"
        bl_file_extensions = ".acf"

        @classmethod
        def poll_drop(cls, context):
            return context.area is not None and context.area.type == "VIEW_3D"

    class IO_FH_xplane_object(bpy.types.FileHandler):
        bl_idname = "IO_FH_xplane_object"
        bl_label = "X-Plane Object"
        bl_import_operator = "import_scene.xplane_obj"
        bl_file_extensions = ".obj"

        @classmethod
        def poll_drop(cls, context):
            return context.area is not None and context.area.type == "VIEW_3D"

    _classes += (IO_FH_xplane_aircraft, IO_FH_xplane_object)


def menu_func_import(self, context):
    self.layout.operator(
        IMPORT_OT_xplane_aircraft.bl_idname, text="X-Plane Aircraft (.acf)"
    )
    self.layout.operator(IMPORT_OT_xplane_obj.bl_idname, text="X-Plane Object (.obj)")


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
