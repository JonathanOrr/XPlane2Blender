"""
The version of the add-on a .blend file was saved with, kept in its history.
"""

import bpy

from io_xplane2blender import xplane_config, xplane_helpers

_version_safety_off = False


class XPlane2BlenderVersion(bpy.types.PropertyGroup):
    r"""
    Contains useful methods for getting information about the
    version and build number of XPlane2Blender

    Names are usually in the format of
    major.minor.release-(alpha|beta|dev|leg|rc)\.[0-9]+)\+\d+\.(YYYYMMDDHHMMSS)
    """

    # Guards against being updated without being validated
    def update_version_property(self, context):
        if _version_safety_off is False:
            raise Exception(
                "Do not modify version property outside of safe_set_version_data!"
            )
        return None

    # Property: addon_version
    #
    # Tuple of Blender addon version, (major, minor, revision)
    addon_version: bpy.props.IntVectorProperty(
        name="XPlane2Blender Addon Version",
        description="The version of the addon (also found in it's addon information)",
        default=xplane_config.CURRENT_ADDON_VERSION,
        update=update_version_property,
        size=3,
    )

    # Property: build_type
    #
    # The type of build this is, always a value in BUILD_TYPES
    build_type: bpy.props.StringProperty(
        name="Build Type",
        description="Which iteration in the development cycle of the chosen build type we're at",
        default=xplane_config.CURRENT_BUILD_TYPE,
        update=update_version_property,
    )

    # Property: build_type_version
    #
    # The iteration in the build cycle, 0 for dev and legacy, > 0 for everything else
    build_type_version: bpy.props.IntProperty(
        name="Build Type Version",
        description="Which iteration in the development cycle of the chosen build type we're at",
        default=xplane_config.CURRENT_BUILD_TYPE_VERSION,
        update=update_version_property,
    )

    # Property: data_model_version
    #
    # The version of the data model, tracked separately. Always incrementing.
    data_model_version: bpy.props.IntProperty(
        name="Data Model Version",
        description="Version of the data model (constants,props, and updater functionality) this version of the addon is. Always incrementing on changes",
        default=xplane_config.CURRENT_DATA_MODEL_VERSION,
        update=update_version_property,
    )

    # Property: build_number
    #
    # If run as a public facing build, this value will be replaced
    # with the YYYYMMSSHHMMSS at build creation date in UTC.
    # Otherwise, it defaults to xplane_constants.BUILD_NUMBER_NONE
    build_number: bpy.props.StringProperty(
        name="Build Number",
        description="Build number of XPlane2Blender. If xplane_constants.BUILD_NUMBER_NONE, this is a development or legacy build!",
        default=xplane_config.CURRENT_BUILD_NUMBER,
        update=update_version_property,
    )

    # Method: safe_set_version_data
    #
    # The only way to change version data! Use responsibly for suffer the Dragons described above!
    # Returns True if it succeeded, or False if it failed due to invalid data. debug_add_to_history only works
    # when the data is valid
    #
    # Passing nothing in results in no change
    def safe_set_version_data(
        self,
        addon_version=None,
        build_type=None,
        build_type_version=None,
        data_model_version=None,
        build_number=None,
        debug_add_to_history=False,
    ):
        if addon_version is None:
            addon_version = self.addon_version
        if build_type is None:
            build_type = self.build_type
        if build_type_version is None:
            build_type_version = self.build_type_version
        if data_model_version is None:
            data_model_version = self.data_model_version
        if build_number is None:
            build_number = self.build_number

        if xplane_helpers.VerStruct(
            addon_version,
            build_type,
            build_type_version,
            data_model_version,
            build_number,
        ).is_valid():
            global _version_safety_off
            _version_safety_off = True
            self.addon_version = addon_version
            self.build_type = build_type
            self.build_type_version = build_type_version
            self.data_model_version = data_model_version
            self.build_number = build_number
            _version_safety_off = False
            if debug_add_to_history:
                xplane_helpers.VerStruct.add_to_version_history(bpy.context.scene, self)
            return True
        else:
            return False

    # Method: make_struct
    #
    # Make a VerStruct version of itself
    def make_struct(self):
        return xplane_helpers.VerStruct(
            self.addon_version,
            self.build_type,
            self.build_type_version,
            self.data_model_version,
            self.build_number,
        )

    # Addon string in the form of "m.m.r", no parenthesis
    def addon_version_clean_str(self):
        return ".".join(map(str, self.addon_version))

    # Method: __repr__
    #
    # repr and repr of VerStruct are the same. It is used as a key for scene.xplane.xplane2blender_ver_history
    def __repr__(self) -> str:
        return "(%s, %s, %s, %s, %s)" % (
            "(" + ",".join(map(str, self.addon_version)) + ")",
            "'" + str(self.build_type) + "'",
            str(self.build_type_version),
            str(self.data_model_version),
            "'" + str(self.build_number) + "'",
        )

    # Method: __str__
    #
    # str and str of VerStruct are the same. It is used for printing to the user
    def __str__(self) -> str:
        return "%s-%s.%s+%s.%s" % (
            ".".join(map(str, self.addon_version)),
            self.build_type,
            self.build_type_version,
            self.data_model_version,
            self.build_number,
        )
