"""Comparing exports to fixture files, line by line with a float tolerance"""

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

FLOAT_TOLERANCE = 0.0001

FilterLinesCallback = Callable[[List[Union[float, str]]], bool]


class FixtureAssertions:
    """The fixture comparing half of XPlaneTestCase"""

    def parseFileToLines(self, data: str) -> List[Tuple[Union[float, str]]]:
        """
        Turns a string of \n seperated lines into a list of lines
        without comments or 0 length strings with all numeric parts are converted
        """
        lines = []  # type: List[Union[float,str]]

        def tryToFloat(part: str) -> Union[float, str]:
            try:
                return float(part)
            except (TypeError, ValueError):
                return part

        for line in filter(lambda l: len(l) > 0 and l[0] != "#", data.split("\n")):
            if "#" in line:
                line = line[0 : line.index("#")]
            line = line.strip()
            if line:
                if line.startswith("800"):
                    lines.append(tuple(line.split()))
                else:
                    lines.append(tuple(map(tryToFloat, line.split())))

        return lines

    def assertFilesEqual(
        self,
        a: str,
        b: str,
        filterCallback: Union[FilterLinesCallback, List[str]],
        floatTolerance: float = FLOAT_TOLERANCE,
    ):
        """
        a and b should be the contents of files a and b as returned
        from open(file).read()
        """

        def isnumber(d):
            return isinstance(d, (float, int))

        linesA = self.parseFileToLines(a)
        linesB = self.parseFileToLines(b)

        # if a filter function is provided, additionally filter lines with it
        if isinstance(filterCallback, collections.abc.Collection):
            linesA = [
                line
                for line in linesA
                if any(directive in line[0] for directive in filterCallback)
            ]
            linesB = [
                line
                for line in linesB
                if any(directive in line[0] for directive in filterCallback)
            ]
        else:
            linesA = list(filter(filterCallback, linesA))
            linesB = list(filter(filterCallback, linesB))

        # ensure same number of lines
        try:
            self.assertEqual(len(linesA), len(linesB))
        except AssertionError as e:
            only_in_a = set(linesA) - set(linesB)
            only_in_b = set(linesB) - set(linesA)
            diff = ">" + "\n>".join(
                " ".join(map(str, l))
                for l in (only_in_a if len(only_in_a) > len(only_in_b) else only_in_b)
            )
            diff += "\n\n>" + "\n>".join(
                " ".join(map(str, l))
                for l in (only_in_a if len(only_in_a) < len(only_in_b) else only_in_b)
            )

            raise AssertionError(
                f"Length of filtered parsed lines unequal: " f"{e.args[0]}\n{diff}\n"
            ) from None

        for lineIndex, (lineA, lineB) in enumerate(zip(linesA, linesB)):
            try:
                # print(f"lineA:{lineA}, lineB:{lineB}")
                self.assertEqual(len(lineA), len(lineB))
            except AssertionError as e:
                raise AssertionError(
                    f"Number of line components unequal: {e.args[0]}\n"
                    f"{lineIndex}> {lineA} ({len(lineA)})\n"
                    f"{lineIndex}> {lineB} ({len(lineB)})"
                ) from None

            for linePos, (segmentA, segmentB) in enumerate(zip(lineA, lineB)):
                # assure same values (floats must be compared with tolerance)
                if isnumber(segmentA) and isnumber(segmentB):
                    # TODO: This is too simple! This will make call abs on the <value> AND <angle> in ANIM_rotate_key
                    # which are not semantically the same!
                    # Also not covered are PHI, PSI, and THETA!
                    segmentA = (
                        abs(segmentA)
                        if "rotate" in lineA[0] or "manip_keyframe" in lineA[0]
                        else segmentA
                    )
                    segmentB = (
                        abs(segmentB)
                        if "rotate" in lineB[0] or "manip_keyframe" in lineB[0]
                        else segmentB
                    )
                    try:
                        self.assertFloatsEqual(segmentA, segmentB, floatTolerance)
                    except AssertionError as e:

                        def make_context(source: List[str], segment: str) -> str:
                            current_line = (
                                f"{lineIndex}> {' '.join(map(str, source[lineIndex]))}"
                            )
                            # Makes something like
                            # 480> ATTR_ -0.45643 1.0 sim/test1
                            # ?          ^~~~~~~~
                            # 480> ATTR_ -1.0 1.0 sim/test1
                            # ?          ^~~~
                            question_line = (
                                "?"
                                + " " * (len(str(lineIndex)) + 3)
                                + "^".rjust(
                                    len(" ".join(map(str, lineA[:linePos]))), " "
                                )
                                + "~" * (len(str(segment)) - 1)
                            )

                            return "\n".join(
                                (
                                    f"{lineIndex - 1}: {' '.join(map(str, source[lineIndex-1]))}"
                                    if lineIndex > 0
                                    else "",
                                    current_line,
                                    question_line,
                                    f"{lineIndex + 1}: {' '.join(map(str, source[lineIndex+1]))}"
                                    if lineIndex + 1 < len(source)
                                    else "",
                                )
                            )

                        context_lineA = make_context(linesA, segmentA)
                        context_lineB = make_context(linesB, segmentB)

                        raise AssertionError(
                            e.args[0]
                            + "\n"
                            + "\n\n".join((context_lineA, context_lineB))
                        ) from None
                else:
                    self.assertEqual(segmentA, segmentB)

    def assertFileOutputEqualsFixture(
        self,
        fileOutput: str,
        fixturePath: str,
        filterCallback: Union[FilterLinesCallback, List[str]],
        floatTolerance: float = FLOAT_TOLERANCE,
    ) -> None:
        """
        Compares the output of XPlaneFile.write (a \n separated str) to a fixture on disk.

        A filterCallback ensures only matching lines are compared.
        Highly recommended, with as simple a function as possible to prevent fixture fragility.
        """

        with open(str(fixturePath), "r") as fixtureFile:
            fixtureOutput = fixtureFile.read()

        # For reviewing fixture changes: the export is written next to a copy of the fixture's path
        # in this folder, to be compared line by line before a fixture is replaced
        review_dir = os.environ.get("XP2B_FIXTURE_REVIEW_DIR")
        if review_dir:
            review_path = Path(review_dir) / Path(fixturePath).resolve().relative_to(Path(__file__).resolve().parents[2])
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(fileOutput)

        return self.assertFilesEqual(
            fileOutput, fixtureOutput, filterCallback, floatTolerance
        )

    def assertFileTmpEqualsFixture(
        self,
        tmpPath: str,
        fixturePath: str,
        filterCallback: Union[FilterLinesCallback, List[str]],
        floatTolerance: float = FLOAT_TOLERANCE,
    ):
        tmpFile = open(tmpPath, "r")
        tmpOutput = tmpFile.read()
        tmpFile.close()

        return self.assertFileOutputEqualsFixture(
            tmpOutput, fixturePath, filterCallback, floatTolerance
        )

    def assertLayerExportEqualsFixture(
        self,
        layer_number: int,
        fixturePath: str,
        filterCallback: Union[FilterLinesCallback, List[str]],
        tmpFilename: Optional[Union[Path,str]] = None,
        floatTolerance: float = FLOAT_TOLERANCE,
    ) -> None:
        """
        DEPRECATED: New unit tests should not use this!

        - layer_number starts at 0, as it used to access the scene.layers collection
        """
        # if not ('-q' in sys.argv or '--quiet' in sys.argv):
        #     print("Comparing: '%s', '%s'" % (tmpFilename, fixturePath))

        out = self.exportExportableRoot(
            bpy.data.collections[f"Layer {layer_number + 1}"], tmpFilename
        )
        self.assertFileOutputEqualsFixture(
            out, fixturePath, filterCallback, floatTolerance
        )

    def assertExportableRootExportEqualsFixture(
        self,
        root_object: Union[bpy.types.Collection, bpy.types.Object, str],
        fixturePath: Union[Path,str],
        filterCallback: Union[FilterLinesCallback, List[str]],
        tmpFilename: Optional[str] = None,
        floatTolerance: float = FLOAT_TOLERANCE,
    ) -> None:
        """
        Exports only a specific exportable root and compares the output
        to a fixutre.

        If filterCallback is a List[str], those directives will be filtered
        will be used. Tip: Use TRIS or POINT_COUNTS instead of VT.
        """
        out = self.exportExportableRoot(root_object, tmpFilename)
        self.assertFileOutputEqualsFixture(
            out, fixturePath, filterCallback, floatTolerance
        )
