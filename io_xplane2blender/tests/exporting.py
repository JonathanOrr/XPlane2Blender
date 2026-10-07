"""Exporting a root from a test, made exportable and visible for the time of the export"""

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

__dirname__ = os.path.dirname(__file__)


def get_tmp_folder() -> pathlib.Path:
    return os.path.realpath(os.path.join(__dirname__, "../../tests/tmp"))


class TemporarilyMakeRootExportable:
    """
    Ensures a potential_root will be exportable
    and when finished, will revert it's exportable
    and viewport settings
    """

    def __init__(
        self,
        potential_root: Union[xplane_helpers.PotentialRoot, str],
        view_layer: Optional[bpy.types.ViewLayer] = None,
    ):
        """
        If view_layer is None, uses current scene's 1st view_layer
        """
        self.view_layer = view_layer or bpy.context.scene.view_layers[0]

        if isinstance(potential_root, str):
            self.potential_root = test_creation_helpers.lookup_potential_root_from_name(
                potential_root
            )
        else:
            self.potential_root = potential_root

        if isinstance(self.potential_root, bpy.types.Collection):
            self.original_exportable = (
                self.potential_root.xplane.is_exportable_collection
            )
            # The little eyeball
            all_layer_collections = {
                lc.name: lc
                for lc in xplane_helpers.get_layer_collections_in_view_layer(
                    self.view_layer
                )
            }
            self.original_hide_viewport = all_layer_collections[
                self.potential_root.name
            ].hide_viewport
        elif isinstance(self.potential_root, bpy.types.Object):
            self.original_exportable = self.potential_root.xplane.isExportableRoot
            # The little eyeball
            self.original_hide_viewport = self.potential_root.hide_get(
                view_layer=self.view_layer
            )
        else:
            assert False, "How did we get here?!"

        self.original_disable_viewport = self.potential_root.hide_viewport

    def __enter__(self):
        test_creation_helpers.make_root_exportable(self.potential_root, self.view_layer)

    def __exit__(self, exc_type, value, traceback):
        if isinstance(self.potential_root, bpy.types.Collection):
            self.potential_root.xplane.is_exportable_collection = (
                self.original_exportable
            )
        elif isinstance(self.potential_root, bpy.types.Object):
            self.potential_root.xplane.isExportableRoot = self.original_exportable

        test_creation_helpers.make_root_unexportable(
            self.potential_root,
            self.view_layer,
            self.original_hide_viewport,
            self.original_disable_viewport,
        )


class Exporting:
    """The exporting half of XPlaneTestCase"""

    def createXPlaneFileFromPotentialRoot(
        self,
        potential_root: Union[xplane_helpers.PotentialRoot, str],
        view_layer: Optional[bpy.types.ViewLayer] = None,
    ) -> xplane_file.XPlaneFile:
        """
        A thin wrapper around xplane_file.createFileFromBlenderObject, where the potential root
        temporarily is made exportable.
        """
        potential_root = (
            test_creation_helpers.lookup_potential_root_from_name(potential_root)
            if isinstance(potential_root, str)
            else potential_root
        )

        view_layer = view_layer or bpy.context.scene.view_layers[0]
        with TemporarilyMakeRootExportable(potential_root, view_layer):
            xp_file = xplane_file.createFileFromBlenderRootObject(
                potential_root, view_layer
            )

        return xp_file

    def exportLayer(
        self, layer_number: int, dest: Optional[Union[Path,str]] = None, force_visible=True
    ) -> str:
        """
        DEPRECATED: New unit tests should not use this!

        - layer_number starts at 0, as it used to access the scene.layers collection
        - dest is a filepath without the file extension .obj, written to the TMP_DIR if not None
        """
        return self.exportExportableRoot(
            bpy.data.collections[f"Layer {layer_number + 1}"], dest, force_visible=True
        )

    def exportExportableRoot(
        self,
        potential_root: Union[xplane_helpers.PotentialRoot, str],
        dest: Optional[Union[Path, str]] = None,
        force_visible=True,
        view_layer: Optional[bpy.types.ViewLayer] = None,
    ) -> str:
        """
        Returns the result of calling xplaneFile.write()

        - dest is a filepath without the file extension .obj, writes result to the TMP_DIR if not None
        - force_visible forces a potential_root to be visible
        - view_layer is needed for checking if potential_root is visible, when None
          the current scene's 1st view layer is used

        If an XPlaneFile could not be made, a ValueError will bubble up
        """
        view_layer = view_layer or bpy.context.scene.view_layers[0]
        assert isinstance(
            potential_root, (bpy.types.Collection, bpy.types.Object, str)
        ), f"root_object type ({type(potential_root)}) isn't allowed, must be Collection, Object, or str"
        if isinstance(potential_root, str):
            try:
                potential_root = bpy.data.collections[potential_root]
            except KeyError:
                try:
                    potential_root = bpy.data.objects[potential_root]
                except KeyError:
                    assert (
                        False
                    ), f"{potential_root} must be in bpy.data.collections|objects"

        if force_visible:
            xp_file = self.createXPlaneFileFromPotentialRoot(potential_root, view_layer)
        else:
            xp_file = xplane_file.createFileFromBlenderRootObject(
                potential_root, view_layer
            )
        out = xp_file.write()
        xplane_file._all_keyframe_infos.clear()

        if dest:
            with open(get_tmp_folder()/Path(dest).with_suffix(".obj"), "w") as tmp_file:
                tmp_file.write(out)

        return out

    @staticmethod
    def get_XPlane2Blender_log_content() -> List[str]:
        """
        Returns the content of the log file after export as a collection of lines, no trailing new lines,
        or KeyError if the text block doesn't exist yet (rare).
        """
        return [l.body for l in bpy.data.texts["XPlane2Blender.log"].lines]
