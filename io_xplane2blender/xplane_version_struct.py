"""
The add-on's version, as written in .blend files to know what to update when one is opened.
"""

import datetime
import re
from datetime import timezone
from typing import Optional, Tuple, Union

import bpy

from io_xplane2blender import xplane_config, xplane_constants, xplane_props


# This is a convenience struct to help prevent people from having to repeatedly copy and paste
# a tuple of all the members of XPlane2BlenderVersion. It is only a data transport struct!
class VerStruct:
    def __init__(
        self,
        addon_version: Optional[Tuple[int, int, int]] = None,
        build_type: Optional[str] = None,
        build_type_version: Optional[int] = None,
        data_model_version: Optional[int] = None,
        build_number: Optional[str] = None,
    ):
        # fmt: off
        self.addon_version      = tuple(addon_version) if addon_version      is not None else (0,0,0)
        self.build_type         = build_type           if build_type         is not None else xplane_constants.BUILD_TYPE_DEV
        self.build_type_version = build_type_version   if build_type_version is not None else 0
        self.data_model_version = data_model_version   if data_model_version is not None else 0
        self.build_number       = build_number         if build_number       is not None else xplane_constants.BUILD_NUMBER_NONE
        # fmt: on

    def __eq__(self, other):
        if tuple(self.addon_version) == tuple(other.addon_version):
            if self.build_type == other.build_type:
                if self.build_type_version == other.build_type_version:
                    if self.data_model_version == other.data_model_version:
                        return True
        return False

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        return (
            self.addon_version,
            xplane_constants.BUILD_TYPES.index(self.build_type),
            self.build_type_version,
            self.data_model_version,
        ) < (
            other.addon_version,
            xplane_constants.BUILD_TYPES.index(other.build_type),
            other.build_type_version,
            other.data_model_version,
        )

    def __gt__(self, other):
        return (
            self.addon_version,
            xplane_constants.BUILD_TYPES.index(self.build_type),
            self.build_type_version,
            self.data_model_version,
        ) > (
            other.addon_version,
            xplane_constants.BUILD_TYPES.index(other.build_type),
            other.build_type_version,
            other.data_model_version,
        )

    def __ge__(self, other):
        return (self > other) or (self == other)

    def __le__(self, other):
        return (self < other) or (self == other)

    # Works for XPlane2BlenderVersion or VerStruct
    def __repr__(self):
        # WARNING! Make sure this is the same as XPlane2BlenderVersion's!!!
        return "(%s, %s, %s, %s, %s)" % (
            "(" + ",".join(map(str, self.addon_version)) + ")",
            "'" + str(self.build_type) + "'",
            str(self.build_type_version),
            str(self.data_model_version),
            "'" + str(self.build_number) + "'",
        )

    def __str__(self):
        # WARNING! Make sure this is the same as XPlane2BlenderVersion's!!!
        return "%s-%s.%s+%s.%s" % (
            ".".join(map(str, self.addon_version)),
            self.build_type,
            self.build_type_version,
            self.data_model_version,
            self.build_number,
        )

    # Method: is_valid
    #
    # Tests if all members of VerStruct are the right type and semantically valid
    # according to our spec
    #
    # Returns True or False
    def is_valid(self) -> bool:
        types_correct = (
            isinstance(self.addon_version, tuple)
            and len(self.addon_version) == 3
            and isinstance(self.build_type, str)
            and isinstance(self.build_type_version, int)
            and isinstance(self.data_model_version, int)
            and isinstance(self.build_number, str)
        )

        if not types_correct:
            raise Exception("Incorrect types passed into VerStruct")

        if (
            self.addon_version[0] >= 3
            and self.addon_version[1] >= 0
            and self.addon_version[2] >= 0
        ):
            if xplane_constants.BUILD_TYPES.index(self.build_type) != -1:
                if (
                    self.build_type == xplane_constants.BUILD_TYPE_DEV
                    or self.build_type == xplane_constants.BUILD_TYPE_LEGACY
                ):
                    if self.build_type_version > 0:
                        print(
                            "build_type_version must be 0 when build_type is %s"
                            % self.build_type
                        )
                        return False
                elif self.build_type_version <= 0:
                    print(
                        "build_type_version must be > 0 when build_type is %s"
                        % self.build_type
                    )
                    return False

                if (
                    self.build_type == xplane_constants.BUILD_TYPE_LEGACY
                    and self.data_model_version != 0
                ):
                    print(
                        "Invalid build_type,data_model_version combo: legacy and data_model_version is not 0"
                    )
                    return False
                elif (
                    self.build_type != xplane_constants.BUILD_TYPE_LEGACY
                    and self.data_model_version <= 0
                ):
                    print(
                        "Invalid build_type,data_model_version combo: non-legacy and data_model_version is > 0"
                    )
                    return False

                if self.build_number == xplane_constants.BUILD_NUMBER_NONE:
                    return True
                else:
                    datetime_matches = re.match(
                        r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", self.build_number
                    )
                    try:
                        # a timezone aware datetime object preforms the validations on construction.
                        dt = datetime.datetime(
                            *[int(group) for group in datetime_matches.groups()],
                            tzinfo=timezone.utc,
                        )
                    except Exception as e:
                        print(
                            "Exception %s occurred while trying to parse datetime" % e
                        )
                        print('"%s" is an invalid build number' % (self.build_number))
                        return False
                    else:
                        return True
            else:
                print("build_type %s was not found in BUILD_TYPES" % self.build_type)
                return False
        else:
            print("addon_version %s is invalid" % str(self.addon_version))
            return False

    @staticmethod
    def add_to_version_history(
        scene: bpy.types.Scene,
        version_to_add: Union["VerStruct", "xplane_props.XPlane2BlenderVersion"],
    ):
        history = scene.xplane.xplane2blender_ver_history

        if len(history) == 0 or history[-1].name != repr(version_to_add):
            new_hist_entry = history.add()
            new_hist_entry.name = repr(version_to_add)
            success = new_hist_entry.safe_set_version_data(
                version_to_add.addon_version,
                version_to_add.build_type,
                version_to_add.build_type_version,
                version_to_add.data_model_version,
                version_to_add.build_number,
            )
            if not success:
                history.remove(len(history) - 1)
                return None
            else:
                return new_hist_entry
        else:
            return False

    # Method: current
    #
    # Returns a VerStruct with all the current xplane_config information.
    # Note: This SHOULD be the same as scene.xplane.xplane2blender_ver, and it is better to use that version.
    # This is provided to reduce error-prone copy and pasting, as needed only!

    @staticmethod
    def current():
        return VerStruct(
            xplane_config.CURRENT_ADDON_VERSION,
            xplane_config.CURRENT_BUILD_TYPE,
            xplane_config.CURRENT_BUILD_TYPE_VERSION,
            xplane_config.CURRENT_DATA_MODEL_VERSION,
            xplane_config.CURRENT_BUILD_NUMBER,
        )

    @staticmethod
    def from_version_entry(
        version_entry: "xplane_props.XPlane2BlenderVersion",
    ) -> "VerStruct":
        return VerStruct(
            version_entry.addon_version,
            version_entry.build_type,
            version_entry.build_type_version,
            version_entry.data_model_version,
            version_entry.build_number,
        )

    @staticmethod
    def make_new_build_number():
        # Use the UNIX Timestamp in UTC
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%d%H%M%S")

    # Method: parse_version
    #
    # Parameters:
    #    version_string: The string to attempt to parse
    # Returns:
    # A valid XPlane2BlenderVersion.VerStruct or None if the parse was unsuccessful
    #
    # Parses a variety of strings and attempts to extract a valid version number and a build number
    # Formats
    # Old version numbers: '3.2.0', '3.2', or '3.3.13'
    # New, moder format: '3.4.0-beta.5+1.20170906154330'
    @staticmethod
    def parse_version(version_str: str) -> Optional["VerStruct"]:
        version_struct = VerStruct()
        # We're dealing with modern
        if version_str.find("-") != -1:
            ######################################
            # Regex matching and data extraction #
            ######################################
            format_str = r"(\d+\.\d+\.\d+)-(alpha|beta|dev|leg|rc)\.(\d+)"

            if "+" in version_str:
                format_str += r"\+(\d+)\.(\w{14})"

            version_matches = re.match(format_str, version_str)

            # Part 1: Major.Minor.revision (1)
            # Part 2: '-' and a build type (2), then a literal '.' and build type number (3)
            # (Optional) literal '+'
            # Part 3: 1 or more digits for data model number (4), a literal '.',
            # then a YYYYMMDDHHMMSS (5)
            if version_matches:
                version_struct.addon_version = tuple(
                    [int(comp) for comp in version_matches.group(1).split(".")]
                )
                version_struct.build_type = version_matches.group(2)
                version_struct.build_type_version = int(version_matches.group(3))

                # If we have a build number, we can take this opportunity to validate it
                if "+" in version_str:
                    version_struct.data_model_version = int(version_matches.group(4))
                    # Regex groups for (hopefully matching) YYYYMMDDHHMMSS
                    version_struct.build_number = version_matches.group(5)
            else:
                return None
        else:
            if re.search(r"[^\d.]", version_str) is not None:
                return None
            else:
                version_struct.addon_version = tuple(
                    [int(v) for v in version_str.split(".")]
                )
                version_struct.build_type = xplane_constants.BUILD_TYPE_LEGACY

        if version_struct.is_valid():
            return version_struct
        else:
            return None


# This a hack to help tests.py catch when an error is an error,
# because everybody and their pet poodle like using the words 'Fail',
#'Error', "FAIL", and "ERROR" making regex impossible.
#
# unittest prints a handy string of .'s, F's, and E's on the first line,
# but due to reasons beyond my grasp, sometimes they don't print a newline
# at the end of it when a failure occurs, making it useless, since we use the word
# "INFO" with an F, meaning you can't search the first line for an F!
#
# Hence this stupid stupid hack, which, is hopefully useful in someway
