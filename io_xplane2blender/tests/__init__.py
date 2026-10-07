import array
import collections
import io
import itertools
import os
import pathlib
from pprint import pprint
import shutil
import sys
import unittest
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import bpy

import io_xplane2blender
from io_xplane2blender import xplane_config, xplane_helpers
from io_xplane2blender.tests import animation_file_mappings, test_creation_helpers
from io_xplane2blender.xplane_config import getDebug, setDebug
from io_xplane2blender.xplane_helpers import XPlaneLogger, logger
from io_xplane2blender.xplane_types import (
    xplane_attribute,
    xplane_attributes,
    xplane_bone,
    xplane_file,
    xplane_primitive,
)

from .exporting import Exporting, TemporarilyMakeRootExportable, get_tmp_folder
from .fixture_assertions import FLOAT_TOLERANCE, FilterLinesCallback, FixtureAssertions

__dirname__ = os.path.dirname(__file__)


class XPlaneTestCase(FixtureAssertions, Exporting, unittest.TestCase):
    def setUp(self, useLogger=True):
        dd_index = sys.argv.index("--")
        blender_args, xplane_args = sys.argv[:dd_index], sys.argv[dd_index + 1 :]
        setDebug("--force-xplane-debug" in xplane_args)

        if useLogger:
            self.useLogger()

        # logger.warn("---------------")

    def useLogger(self):
        debug = getDebug()
        logLevels = ["error", "warning"]

        if debug:
            logLevels.append("info")
            logLevels.append("success")

        logger.clear()
        logger.addTransport(XPlaneLogger.ConsoleTransport(), logLevels)

    def assertImagesEqual(
        self,
        img_a: Union[bpy.types.Image, Path, str],
        img_b: Union[bpy.types.Image, Path, str],
        channels=0b1111,
    ):
        """Asserts two images are equal by comparing their pixel buffers.

        If img_a/b are Paths, they will be loaded as Image blocks (check_existing=True) and removed later
        The specified channels of each image's pixel buffers will be compared to x places
        """
        # Thank you once again senderle!, https://stackoverflow.com/a/22045226
        def chunk(it, size):
            it = iter(it)
            return iter(lambda: tuple(itertools.islice(it, size)), ())

        try:
            if isinstance(img_a, (Path, str)):
                cmp_img_a = test_creation_helpers.create_datablock_image_from_disk(
                    img_a
                )
            if isinstance(img_b, (Path, str)):
                cmp_img_b = test_creation_helpers.create_datablock_image_from_disk(
                    img_b
                )
            self.assertEqual(
                cmp_img_a.size[:],
                cmp_img_b.size[:],
                msg=f"Images must be same size, are {cmp_img_a.size} and {cmp_img_b.size}",
            )
            self.assertNotEqual(
                cmp_img_a.size,
                (0, 0),
                msg=f"Image data for {cmp_img_a.name} could not be loaded",
            )
            self.assertNotEqual(
                cmp_img_b.size,
                (0, 0),
                msg=f"Image data for {cmp_img_b.name} could not be loaded",
            )

            a_pixels = chunk(array.array("f", cmp_img_a.pixels), 4)
            b_pixels = chunk(array.array("f", cmp_img_b.pixels), 4)
        finally:
            bpy.data.images.remove(cmp_img_a)
            bpy.data.images.remove(cmp_img_b)

        for i, ((a_pixel), (b_pixel)) in enumerate(zip(a_pixels, b_pixels)):
            if 0b1000 & channels:
                self.assertAlmostEqual(a_pixel[0], b_pixel[0], 8, msg=f"in Red channel")
            if 0b0100 & channels:
                self.assertAlmostEqual(
                    a_pixel[1], b_pixel[1], 8, msg=f"in Green channel"
                )
            if 0b0010 & channels:
                self.assertAlmostEqual(
                    a_pixel[2], b_pixel[2], 8, msg=f"in Blue channel"
                )
            if 0b0001 & channels:
                self.assertAlmostEqual(
                    a_pixel[3], b_pixel[3], 8, msg=f"in Alpha channel"
                )

    def assertMatricesEqual(self, mA, mB, tolerance=FLOAT_TOLERANCE):
        for row_a, row_b in zip(mA, mB):
            self.assertFloatVectorsEqual(row_a, row_b, tolerance)

    # Utility method to check if objects are contained in file
    def assertObjectsInXPlaneFile(self, xplaneFile, objectNames):
        for name in objectNames:
            # TODO:  Remove/change
            self.assertIsNotNone(xplaneFile._bl_obj_name_to_bone[name])
            self.assertTrue(
                isinstance(
                    xplaneFile._bl_obj_name_to_bone[name].xplaneObject,
                    xplane_primitive.XPlanePrimitive,
                )
            )
            self.assertEqual(
                xplaneFile._bl_obj_name_to_bone[name].blenderObject,
                bpy.data.objects[name],
            )

    def assertXPlaneBoneTreeEqual(
        self,
        file_root_bone: xplane_bone.XPlaneBone,
        fixture_root_bone: xplane_bone.XPlaneBone,
    ) -> None:
        """
        Recurses down two XPlaneBone trees, and compares each XPlaneBone's
        - xplaneObject
        - blenderObject
        - blenderBone

        self.xplaneFile and self.parent are not compared
        """
        assert file_root_bone
        assert fixture_root_bone

        def recursively_check(
            file_bone: xplane_bone.XPlaneBone, fixture_bone: xplane_bone.XPlaneBone
        ) -> None:
            file_bone_name = getattr(file_bone.xplaneObject, "name", "None")
            fixture_bone_name = getattr(fixture_bone.xplaneObject, "name", "None")
            self.assertEqual(
                bool(file_bone.xplaneObject),
                bool(fixture_bone.xplaneObject),
                msg=f"File Bone '{file_bone.getName(ignore_indent_level=True)}'"
                f" and Fixture Bone '{file_bone.getName(ignore_indent_level=True)}'"
                f" don't have the same xplaneObject: ({file_bone_name, fixture_bone_name}),",
            )
            self.assertEqual(file_bone.blenderObject, fixture_bone.blenderObject)
            self.assertEqual(file_bone.blenderBone, fixture_bone.blenderBone)
            self.assertEqual(len(file_bone.children), len(fixture_bone.children))
            for child_file_bone, child_fixture_bone in zip(
                file_bone.children, fixture_bone.children
            ):
                recursively_check(child_file_bone, child_fixture_bone)

        recursively_check(file_root_bone, fixture_root_bone)

    def assertFloatsEqual(self, a: float, b: float, tolerance: float = FLOAT_TOLERANCE):
        """
        Tests if floats are equal, with a default tollerance. The difference between this and assertAlmostEqual
        is that we use abs instead of round, then compare
        """
        if abs(a - b) < tolerance:
            return True
        else:
            raise AssertionError(f"{a} != {b}, within a tolerance of {tolerance}")

    def assertFloatVectorsEqual(
        self, a: int, b: int, tolerance: float = FLOAT_TOLERANCE
    ):
        self.assertEqual(len(a), len(b))
        for a_comp, b_comp in zip(a, b):
            self.assertFloatsEqual(a_comp, b_comp, tolerance)

    def assertLoggerErrors(self, expected_logger_errors: int) -> None:
        """
        Asserts the logger has some number of errors, then clears the logger
        of all messages
        """
        try:
            found_errors = len(logger.findErrors())
            self.assertEqual(found_errors, expected_logger_errors)
        except AssertionError as e:
            raise AssertionError(
                f"Expected {expected_logger_errors} logger errors, got {found_errors}"
            ) from None
        else:
            logger.clearMessages()

    # TODO: Must filter warnings to have this be useful
    # Method: assertLoggerWarnings
    #
    # expected_logger_warnings - The number of warnings you expected to have happen
    # asserts the number of warnings and clears the logger of all messages
    # def assertLoggerWarnings(self, expected_logger_warnings):
    #    self.assertEqual(len(logger.findWarnings()), expected_logger_warnings)
    #    logger.clearMessages()

    # asserts that an attributes object equals a dict
    def assertAttributesEqualDict(
        self,
        attrs: xplane_attributes.XPlaneAttributes,
        expected_attrs: Dict[
            str,
            Union[
                xplane_attribute.AttributeValueType,
                xplane_attribute.AttributeValueTypeList,
            ],
        ],
        floatTolerance: float = FLOAT_TOLERANCE,
    ):
        with io.StringIO() as s_buf:
            pprint(list(expected_attrs.keys()), s_buf)
            d_pp_str = s_buf.getvalue()
        with io.StringIO() as s_buf:
            pprint(list(attrs.keys()), s_buf)
            attrs_pp_str = s_buf.getvalue()
        self.assertEqual(
            len(expected_attrs),
            len(attrs),
            f"Attribute lists {list(expected_attrs.keys())}, {list(attrs.keys())} have different length",
        )

        for name in attrs.keys():
            value = attrs[name].getValue()
            expected_value = expected_attrs[name]

            if isinstance(expected_value, (list, tuple)):
                self.assertIsInstance(
                    value,
                    (list, tuple),
                    msg='Attribute value for "{value}" is a {type(value)}, not a list or tuple',
                )
                self.assertEqual(
                    len(expected_value),
                    len(value),
                    'Attribute value list for "{name}" have different length',
                )

                for i, (v, expectedV) in enumerate(zip(value, expected_value)):
                    if isinstance(expectedV, (float, int)):
                        self.assertFloatsEqual(expectedV, v, floatTolerance)
                    else:
                        self.assertEqual(
                            expectedV,
                            v,
                        )
            else:
                self.assertEqual(
                    expected_value,
                    value,
                )


class XPlaneAnimationTestCase(XPlaneTestCase):
    def setUp(self):
        super(XPlaneAnimationTestCase, self).setUp()

    def _clearLayerTexture(self, layer: int) -> None:
        # Animation fixtures only compare ANIM and TRIS lines, but some of the .blend
        # files carry an absolute texture path with spaces from the author's machine,
        # which is now (rightly) a validation error
        bpy.data.collections[f"Layer {layer + 1}"].xplane.layer.texture = ""

    def exportAnimationTestCase(self, name, dest):
        self.assertTrue(animation_file_mappings.mappings[name])

        for layer in animation_file_mappings.mappings[name]:
            outFile = os.path.join(
                dest, os.path.basename(animation_file_mappings.mappings[name][layer])
            )
            print('Exporting to "%s"' % outFile)

            self._clearLayerTexture(layer)
            io_xplane2blender.tests.test_creation_helpers.make_root_exportable(
                bpy.data.collections[f"Layer {layer + 1}"]
            )
            try:
                xplaneFile = xplane_file.createFileFromBlenderRootObject(
                    bpy.data.collections[f"Layer {layer + 1}"],
                    bpy.context.scene.view_layers[0],
                )
            except xplane_file.NotExportableRootError:
                assert (
                    False
                ), f"Unable to create XPlaneFile for {name} from Layer {layer + 1}"
            else:
                with open(outFile, "w") as outFile:
                    out = xplaneFile.write()
                    outFile.write(out)

    def runAnimationTestCase(self, name, __dirname__):
        self.assertTrue(animation_file_mappings.mappings[name])

        def filterLine(line):
            # only keep ANIM_ lines
            return isinstance(line[0], str) and ("ANIM" in line[0] or "TRIS" in line[0])

        for layer in animation_file_mappings.mappings[name]:
            # print('Testing animations against fixture "%s"' % mappings[name][layer])
            self._clearLayerTexture(layer)
            bpy.data.collections[f"Layer {layer + 1}"].hide_viewport = False
            xplaneFile = self.createXPlaneFileFromPotentialRoot(
                bpy.data.collections[f"Layer {layer + 1}"]
            )

            self.assertIsNotNone(
                xplaneFile,
                "Unable to create XPlaneFile for %s layer %d" % (name, layer),
            )

            out = xplaneFile.write()
            fixtureFile = os.path.join(
                __dirname__, animation_file_mappings.mappings[name][layer]
            )

            self.assertTrue(
                os.path.exists(fixtureFile), 'File "%s" does not exist' % fixtureFile
            )
            self.assertFileOutputEqualsFixture(out, fixtureFile, filterLine)


def get_source_folder() -> pathlib.Path:
    """Returns the full path to the addon folder"""
    return pathlib.Path(__file__).parent


def get_project_folder() -> pathlib.Path:
    """Returns the full path to the project folder"""
    return pathlib.Path(__file__).parent.parent.parent


def get_tests_folder() -> pathlib.Path:
    return pathlib.Path(get_project_folder(), "tests")


def make_fixture_path(dirname, filename, sub_dir=""):
    return os.path.join(dirname, "fixtures", sub_dir, filename + ".obj")


def runTestCases(testCases):
    # Until a better solution for knowing if the logger's error count should be used to quit the testing,
    # we are currently saying only 1 is allow per suite at a time (which is likely how it should be anyways)
    assert (
        len(testCases) == 1
    ), "Currently, only one test case per suite is supported at a time"
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(testCases[0])
    test_result = unittest.TextTestRunner().run(suite)

    # See XPlane2Blender/tests.py for documentation. The strings must be kept in sync!
    # This is not an optional debug print statement! The test runner needs this print statement to function
    print(
        f"RESULT: After {(test_result.testsRun)} tests got {len(test_result.errors)} errors, {len(test_result.failures)} failures, and {len(test_result.skipped)} skipped"
    )
