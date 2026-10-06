"""Operators and menu entries for importing X-Plane objects and aircraft"""
import os

import bpy
from bpy_extras.io_utils import ImportHelper

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
            name="Lights", description="Create X-Plane lights as Blender lights", default=True
        ),
        "hide_default_hidden": bpy.props.BoolProperty(
            name="Hide What X-Plane Hides",
            description="Hide the show/hide objects that X-Plane would not draw with the datarefs at their default values. "
            "Unhide them before exporting again, hidden objects are not exported",
            default=True,
        ),
        "all_lods": bpy.props.BoolProperty(
            name="All LODs", description="Import every level of detail instead of only the first", default=False
        ),
        "setup_for_export": bpy.props.BoolProperty(
            name="Set Up For Export",
            description="Make each imported OBJ an XPlane2Blender root collection with its textures set, ready to export again",
            default=True,
        ),
        "lit_strength": bpy.props.FloatProperty(
            name="Night Light Strength",
            description="How bright the _LIT texture glows. 0 shows the daytime look",
            default=0.0,
            min=0.0,
            soft_max=10.0,
        ),
        "scale": bpy.props.FloatProperty(
            name="Scale", description="Multiplies all sizes. X-Plane uses meters, like Blender's default", default=1.0, min=0.0001
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
        "setup_for_export",
        "lit_strength",
        "scale",
    )
    return ImportOptions(**{k: getattr(op, k) for k in keys if hasattr(op, k)})


def _show_report(operator, report: ImportReport) -> None:
    operator.report({"INFO"}, report.summary())
    for warning in report.warnings[:8]:
        operator.report({"WARNING"}, warning)
    for error in report.errors[:8]:
        operator.report({"ERROR"}, error)
    if len(report.warnings) > 8:
        operator.report({"WARNING"}, f"...and {len(report.warnings) - 8} more warnings, see the System Console")
    for line in report.warnings + report.errors:
        print("XPlane2Blender import:", line)


class IMPORT_OT_xplane_obj(bpy.types.Operator, ImportHelper):
    """Import X-Plane objects (.obj), with their textures, animations and manipulators"""

    bl_idname = "import.xplane_obj"
    bl_label = "Import X-Plane Object"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    filename_ext = ".obj"
    filter_glob: bpy.props.StringProperty(default="*.obj", options={"HIDDEN"})
    files: bpy.props.CollectionProperty(type=bpy.types.OperatorFileListElement, options={"HIDDEN", "SKIP_SAVE"})
    directory: bpy.props.StringProperty(subtype="DIR_PATH")

    __annotations__.update(_option_properties())

    def execute(self, context):
        report = ImportReport()
        options = _options_from(self)
        paths = [os.path.join(self.directory, f.name) for f in self.files] or [self.filepath]
        for path in paths:
            import_obj_file(path, options, report)
        _show_report(self, report)
        return {"FINISHED"} if report.files_imported else {"CANCELLED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        box = layout.box()
        box.label(text="Bring in", icon="IMPORT")
        for name in ("import_materials", "import_animations", "import_manipulators", "import_lights", "all_lods", "hide_default_hidden"):
            box.prop(self, name)
        box = layout.box()
        box.label(text="Setup", icon="PREFERENCES")
        box.prop(self, "setup_for_export")
        box.prop(self, "lit_strength")
        box.prop(self, "scale")


_livery_items_cache = {}


def _livery_items(self, context):
    """Dropdown entries for the liveries of the aircraft that is selected in the file browser"""
    items = [("", "Default textures", "Use the textures the objects ask for")]
    path = bpy.path.abspath(self.filepath) if self.filepath else ""
    if path.lower().endswith(".acf") and os.path.isfile(path):
        folder = os.path.join(os.path.dirname(path), "liveries")
        try:
            names = sorted(e for e in os.listdir(folder) if os.path.isdir(os.path.join(folder, e)))
        except OSError:
            names = []
        items += [(n, n, f"Textures from the {n} livery") for n in names]
    # Blender needs the strings to stay alive
    _livery_items_cache["items"] = items
    return items


class IMPORT_OT_xplane_aircraft(bpy.types.Operator, ImportHelper):
    """Import a whole X-Plane aircraft from its .acf file: every object, with textures, animations and manipulators"""

    bl_idname = "import.xplane_aircraft"
    bl_label = "Import X-Plane Aircraft"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    filename_ext = ".acf"
    filter_glob: bpy.props.StringProperty(default="*.acf", options={"HIDDEN"})

    livery: bpy.props.EnumProperty(name="Livery", description="Which set of textures to use", items=_livery_items)
    include_damage: bpy.props.BoolProperty(
        name="Damage Objects", description="Also import the objects that only show when a part breaks", default=False
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
        livery = self.livery if self.livery else ""
        root = import_aircraft(
            bpy.path.abspath(self.filepath),
            options,
            report,
            livery=livery,
            include_damage=self.include_damage,
            include_attached=self.include_attached,
        )
        _show_report(self, report)
        return {"FINISHED"} if root is not None and report.files_imported else {"CANCELLED"}

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        box = layout.box()
        box.label(text="Aircraft", icon="OBJECT_DATA")
        box.prop(self, "livery")
        box.prop(self, "include_damage")
        box.prop(self, "include_attached")
        box = layout.box()
        box.label(text="Bring in", icon="IMPORT")
        for name in ("import_materials", "import_animations", "import_manipulators", "import_lights", "all_lods", "hide_default_hidden"):
            box.prop(self, name)
        box = layout.box()
        box.label(text="Setup", icon="PREFERENCES")
        box.prop(self, "setup_for_export")
        box.prop(self, "lit_strength")
        box.prop(self, "scale")


_classes = (IMPORT_OT_xplane_obj, IMPORT_OT_xplane_aircraft)


def menu_func_import(self, context):
    self.layout.operator(IMPORT_OT_xplane_aircraft.bl_idname, text="X-Plane Aircraft (.acf)")
    self.layout.operator(IMPORT_OT_xplane_obj.bl_idname, text="X-Plane Object (.obj)")


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
