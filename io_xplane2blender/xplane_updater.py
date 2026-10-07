"""
Brings .blend files saved by older versions up to date when they are opened, and records which
versions of the add-on each file has been opened with.

Re-running an update must change nothing, and only what is needed is changed.
"""
import bpy
from bpy.app.handlers import persistent

from io_xplane2blender import xplane_constants, xplane_helpers, xplane_xp12
from io_xplane2blender import xplane_updater_legacy as legacy
from io_xplane2blender.xplane_helpers import XPlaneLogger
from io_xplane2blender.xplane_utils import xplane_updater_helpers


def update(
    last_version: xplane_helpers.VerStruct, logger: xplane_helpers.XPlaneLogger
) -> None:
    """
    Entry point for the updater, which may change or delete XPlane2Blender
    properties of this .blend file to match the data model of this version of XPlane2Blender.
    Adding new properties to the data model is done elsewhere.

    Re-running the updater should result in no changes
    """
    if last_version < xplane_helpers.VerStruct.parse_version("4.3.2"):
        legacy.update_light_intensities(logger)
            
    if last_version < xplane_helpers.VerStruct.parse_version("4.0.0"):
        legacy.layers_to_collection(logger)

    if last_version < xplane_helpers.VerStruct.parse_version("3.3.0"):
        legacy.change_pre_3_3_0_properties(logger)

    if last_version < xplane_helpers.VerStruct.parse_version("3.4.0"):
        for arm in bpy.data.armatures:
            for bone in arm.bones:
                # Thanks to Python's duck typing and Blender's PointerProperties, this works
                legacy.update_LocRot(bone, logger)

        for obj in bpy.data.objects:
            legacy.update_LocRot(obj, logger)

    if last_version < xplane_helpers.VerStruct.parse_version(
        "3.5.0-beta.2+32.20180725010500"
    ):
        legacy.rollback_blend_glass(logger)

    if last_version < xplane_helpers.VerStruct.parse_version(
        "3.5.1-dev.0+43.20190606030000"
    ):
        legacy.set_shadow_local_and_delete_global_shadow(logger)

    if last_version < xplane_helpers.VerStruct.parse_version(
        "4.0.0-alpha.6+71.20200207171400"
    ):
        # --- Disable autodetect textures --------------------------------------

        for has_layer in bpy.data.collections[:] + bpy.data.objects[:]:
            xplane_updater_helpers.delete_property_from_datablock(
                has_layer.xplane.layer, "autodetectTextures"
            )
        # --- Delete "exportMode" ----------------------------------------------
        for scene in bpy.data.scenes:
            xplane_updater_helpers.delete_property_from_datablock(
                scene.xplane, "exportMode"
            )
        # ----------------------------------------------------------------------
        # --- Delete index -----------------------------------------------------
        for has_layer in bpy.data.collections[:] + bpy.data.objects[:]:
            xplane_updater_helpers.delete_property_from_datablock(
                has_layer.xplane.layer, "index"
            )
        # ----------------------------------------------------------------------
        # --- Delete XPlaneObjectSettings.export_mesh---------------------------
        for obj in bpy.data.objects:
            xplane_updater_helpers.delete_property_from_datablock(
                obj.xplane, "export_mesh"
            )
        # ----------------------------------------------------------------------
        # --- Delete all XPlaneLayer's "Include in Export" ---------------------
        for has_layer in bpy.data.collections[:] + bpy.data.objects[:]:
            xplane_updater_helpers.delete_property_from_datablock(
                has_layer.xplane.layer, "export"
            )
        # ----------------------------------------------------------------------

    if last_version < xplane_helpers.VerStruct.parse_version(
        "4.0.0-beta.2+88.20200622133200"
    ):
        # Remember, get returning 0 and return None means something different.
        # 0 was the X-Plane 9 "default" light, which convert_to_xp12 replaces
        for light in filter(lambda l: l.xplane.get("type") is None, bpy.data.lights):
            light.xplane["type"] = 0

    if last_version < xplane_helpers.VerStruct.parse_version(
        "4.1.0-alpha.1+92.20201020151500"
    ):
        legacy.move_global_material_props(logger)
    if last_version < xplane_helpers.VerStruct.parse_version(
        "4.1.0-alpha.1+97.20201109172400"
    ):
        legacy.panel_to_cockpit_feature(logger)
    if last_version < xplane_helpers.VerStruct.parse_version(
        "4.1.0-beta.1+100.20201117112800"
    ):
        legacy.regions_change_panel_mode(logger)

    # Version 5 makes X-Plane 12 aircraft only
    if tuple(last_version.addon_version) < (5, 0, 0):
        for change in xplane_xp12.convert_to_xp12():
            logger.info(change)


def _synchronize_last_version_across_histories(last_version: xplane_helpers.VerStruct):
    assert last_version.is_valid(), f"last_version {last_version} isn't valid"

    for scene in bpy.data.scenes:
        xplane_helpers.VerStruct.add_to_version_history(scene, last_version)


@persistent
def load_handler(dummy):
    from io_xplane2blender.xplane_utils import xplane_lights_txt_parser

    # --- Setup logger (Startup) ----------------------------------------------
    logger = xplane_helpers.logger
    logger.clear()
    logger.addTransport(
        xplane_helpers.XPlaneLogger.InternalTextTransport("Startup Log"),
        xplane_constants.LOGGER_LEVELS_ALL,
    )
    logger.addTransport(XPlaneLogger.ConsoleTransport())
    # -------------------------------------------------------------------------
    # --- Parse lights.txt file -----------------------------------------------
    try:
        xplane_lights_txt_parser.parse_lights_file()
    except (FileNotFoundError, OSError) as oe:
        message = str(oe)

        def draw(self, context):
            self.layout.label(
                text="Some lighting features may not work. Read the internal text block 'Startup Log' for more details"
            )
            self.layout.label(
                text="Check for a missing or broken lights.txt file or re-install addon"
            )
            self.layout.label(text=message)

        bpy.context.window_manager.popup_menu(
            draw,
            title="Could not read io_xplane2blender/resources/lights.txt",
            icon="ERROR",
        )
    except xplane_lights_txt_parser.LightsTxtFileParsingError as pe:
        message = str(pe)

        def draw(self, context):
            self.layout.label(
                text="Some lighting features may not work. Read the internal text block 'Startup Log' for more details"
            )
            self.layout.label(
                text="Check replace lights.txt from X-Plane or re-install addon"
            )
            self.layout.label(text=message)

        bpy.context.window_manager.popup_menu(
            draw,
            title="io_xplane2blender/resources/lights.txt had invalid content",
            icon="ERROR",
        )
    # -------------------------------------------------------------------------

    # --- Add/Correct Layer Props ---------------------------------------------
    for layer_props in [
        has_layer_props.xplane.layer
        for has_layer_props in bpy.data.objects[:] + bpy.data.collections[:]
    ]:
        # Since someone could add lods/cockpit_regions just before export, export needs to be the one
        # to validate the size of the collection
        while len(layer_props.lod) < xplane_constants.MAX_LODS - 1:
            layer_props.lod.add()
        while len(layer_props.cockpit_region) < xplane_constants.MAX_COCKPIT_REGIONS:
            layer_props.cockpit_region.add()
    # -------------------------------------------------------------------------

    # do not update newly created files
    if not bpy.context.blend_data.filepath:
        return

    assert bpy.data.filepath, "We've missed the new file check"
    # --- Setup logger (Updater) ----------------------------------------------
    logger.clear()
    logger.addTransport(
        xplane_helpers.XPlaneLogger.InternalTextTransport("Updater Log"),
        xplane_constants.LOGGER_LEVELS_ALL,
    )
    logger.addTransport(XPlaneLogger.ConsoleTransport())
    # -------------------------------------------------------------------------

    current_version = xplane_helpers.VerStruct.current()

    def handle_legacy_idprop(scene: bpy.types.Scene):
        if scene.get("xplane2blender_version") != xplane_constants.DEPRECATED_XP2B_VER:
            # "3.2.0 was the last version without an updater, so default to that."
            # 3.20 was a mistake
            legacy_version_str = scene.get("xplane2blender_version", "3.2.0").replace(
                "20", "2"
            )
            legacy_version = xplane_helpers.VerStruct.parse_version(legacy_version_str)
            if legacy_version is not None:
                xplane_helpers.VerStruct.add_to_version_history(scene, legacy_version)
                logger.info(f"Added {legacy_version} to version history")

                scene["xplane2blender_version"] = xplane_constants.DEPRECATED_XP2B_VER
            else:
                logger.warn(
                    f"pre-3.4.0-beta.5 file has invalid xplane2blender_version: {legacy_version_str}.\n"
                    f"Re-open file in a previous version and/or fix manually in Scene->Custom Properties"
                )

    for scene in bpy.data.scenes:
        handle_legacy_idprop(scene)

    latest_versions = sorted(
        (
            xplane_helpers.VerStruct.from_version_entry(
                scene.xplane.xplane2blender_ver_history[-1]
            )
            for scene in bpy.data.scenes
            if scene.xplane.xplane2blender_ver_history
        ),
    )
    assert latest_versions, "Non-newly created file has no scene with version history"
    last_version = latest_versions[-1]

    if last_version < current_version:
        logger.info(
            f"The current addon version, '{current_version}', is greater than the previous version, '{last_version}'. The updater will run as needed."
        )
        update(last_version, logger)

        logger.success(
            f"Your file was successfully updated to XPlane2Blender {current_version}"
        )
    elif last_version > current_version:
        logger.warn(
            f"DANGER: VERSION ISSUE MAY CORRUPT WORK! CHECK BLENDER AND ADDON VERSION. You have opened this file in an older version of XPlane2Blender."
            f" If saved and opened with a later version, the updater may re-run and overwrite data."
        )

    # Add the current version to the history, no matter what. Just in case it means something
    _synchronize_last_version_across_histories(current_version)
    logger.info(f"Added '{current_version}' to version history")


bpy.app.handlers.load_post.append(load_handler)


@persistent
def save_handler(dummy):
    for scene in bpy.data.scenes:
        scene["xplane2blender_version"] = xplane_constants.DEPRECATED_XP2B_VER
    # For if you append or make a new scene
    _synchronize_last_version_across_histories(xplane_helpers.VerStruct.current())


bpy.app.handlers.save_pre.append(save_handler)
