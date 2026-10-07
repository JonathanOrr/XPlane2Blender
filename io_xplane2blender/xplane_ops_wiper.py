"""
Baking the wiper gradient texture of a file's rain settings from the wiper animation.
"""

import shutil
import time
from pathlib import Path
from typing import List, Optional

import bpy

from io_xplane2blender import xplane_props
from io_xplane2blender.xplane_helpers import get_active_export_root, logger
from io_xplane2blender.xplane_utils import xplane_wiper_gradient


# This code is based off of Christian Brinkmann (p2or)
# and Janne Karhu (jahka)'s "Sequency Bakery" Addon. It is also released under
# the same GPL license as XPlane2Blender
def _root(name: str, context):
    """A file (collection or root object) by name, or the active object's or collection's"""
    if name:
        return bpy.data.collections.get(name) or bpy.data.objects.get(name)
    return get_active_export_root(context.active_object, context.collection)


class XPLANE_OT_bake_wiper_gradient_texture(bpy.types.Operator):
    bl_label = "Make Wiper Gradient Texture"
    bl_idname = "xplane.bake_wiper_gradient_texture"
    bl_description = "Makes the Wiper Gradient Texture from the Rain Settings of the active collection (may take more than 30 minutes)"

    # The file to bake for; without one, the active object's or collection's
    file: bpy.props.StringProperty(options={"HIDDEN"})

    # fmt: off
    start: bpy.props.IntProperty(
        name="Start",
        description="Specifies which frame to start baking",
        default=1,
        min=1,
    )

    debug_master_filepath: bpy.props.StringProperty(
        "Override Final Texture Path",
        description="Manual override to set the finished image. Can include '//'.",
    )

    debug_reuse_temps: bpy.props.BoolProperty(
        name="Re-use Temporary Images",
        description="Reuse temporaries instead of re-baking, temp files aren't deleted",
        default=False,
    )

    debug_slots: bpy.props.BoolVectorProperty(
        "Slots To Bake",
        description="'False' slots are skipped, without preventing slots afterwards from being baked themselves",
        default=(True,) * 4,
        size=4,
    )
    # fmt: on

    @classmethod
    def poll(cls, context):
        scene_files = (c.xplane.is_exportable_collection for c in context.scene.collection.children_recursive)
        return _root("", context) is not None or any(scene_files)

    def execute(self, context):
        scene = context.scene
        if scene.render.engine != "CYCLES":
            bpy.ops.xplane.msg(
                "INVOKE_DEFAULT",
                msg_text="Baking the wiper gradient requires the Cycles render engine",
            )
            return {"CANCELLED"}

        active_root = _root(getattr(self, "file", ""), context)
        if active_root is None:
            msg = "Select an exportable root to bake the wiper gradient texture"
            logger.error(msg)
            bpy.ops.xplane.msg("INVOKE_DEFAULT", msg_text=msg)
            return {"CANCELLED"}
        rain = active_root.xplane.layer.rain

        try:
            windshield = bpy.data.objects[rain.wiper_ext_glass_object]
        except KeyError:
            if rain.wiper_ext_glass_object:
                msg = f"Cannot find '{rain.wiper_ext_glass_object}' to be used for exterior glass. Check your spelling in the Rain Settings"
            else:
                msg = f"Must specify object to be used as the exterior glass. Check your Rain Settings"

            bpy.ops.xplane.msg("INVOKE_DEFAULT", msg_text=msg)
            return {"CANCELLED"}

        def collect_wipers() -> List[xplane_props.XPlaneWiperSettings]:
            wipers = []
            for idx in range(1, 5):
                if getattr(rain, f"wiper_{idx}_enabled"):
                    wiper = getattr(rain, f"wiper_{idx}")
                    try:
                        object_name = wiper.object_name
                        object_datablock = bpy.data.objects[object_name]
                    except KeyError:
                        if object_name:
                            msg = f"Could not find '{object_name}'. Check your spelling"
                        else:
                            msg = f"Wiper slot #{idx} must have an object name"
                        bpy.ops.xplane.msg("INVOKE_DEFAULT", msg_text=msg)
                        raise
                    else:
                        wipers.append(wiper)
                else:
                    break
            return wipers

        try:
            wipers = collect_wipers()
        except KeyError:
            # collect_wipers ensures object_names are given and correct
            return {"CANCELLED"}
        else:
            if not wipers:
                bpy.ops.xplane.msg(
                    "INVOKE_DEFAULT", msg_text="Must have at least 1 wiper enabled"
                )
                return {"CANCELLED"}

        def find_baking_node(
            bake_object: bpy.types.Object,
        ) -> Optional[bpy.types.ShaderNodeTexImage]:
            """Finds the image texture node Cycles will bake to"""
            # XXX This tries to mimic nodeGetActiveTexture(), but we have no access to 'texture_active' state from RNA...
            #     IMHO, this should be a func in RNA nodetree struct anyway?
            inactive = None
            selected = None
            for mat_slot in bake_object.material_slots:
                mat = mat_slot.material
                if not mat or not mat.node_tree:
                    continue
                trees = [mat.node_tree]
                while trees:
                    tree = trees.pop()
                    node = tree.nodes.active
                    if node and node.type in {"TEX_IMAGE", "TEX_ENVIRONMENT"} and node.image:
                        return node
                    for node in tree.nodes:
                        if (
                            node.type in {"TEX_IMAGE", "TEX_ENVIRONMENT"}
                            and node.image
                        ):
                            if node.select:
                                if not selected:
                                    selected = node
                            else:
                                if not inactive:
                                    inactive = node
                        elif node.type == "GROUP" and node.node_tree:
                            trees.append(node.node_tree)
            return selected or inactive

        # --- Errors with what you're trying to bake --------------------------
        # Only single object baking for now
        if windshield.type != "MESH":
            bpy.ops.xplane.msg(
                "INVOKE_DEFAULT",
                msg_text=f"The baked object must be a mesh object, is {windshield.type.title()}",
            )
            return {"CANCELLED"}

        if windshield.mode == "EDIT":
            bpy.ops.xplane.msg("INVOKE_DEFAULT", msg_text="Can't bake in edit-mode")
            return {"CANCELLED"}
        # ---------------------------------------------------------------------
        bake_node = find_baking_node(windshield)
        # --- Errors with the bake image --------------------------------------
        if bake_node is None:
            bpy.ops.xplane.msg(
                "INVOKE_DEFAULT", msg_text="No valid image found to bake to"
            )
            return {"CANCELLED"}

        img = bake_node.image
        img_filepath = Path(bpy.path.abspath(img.filepath, library=img.library))

        if img.is_dirty:
            bpy.ops.xplane.msg(
                "INVOKE_DEFAULT",
                msg_text="Save the image that's used for baking before use",
            )
            return {"CANCELLED"}

        if img.packed_file is not None:
            bpy.ops.xplane.msg(
                "INVOKE_DEFAULT", msg_text="Can't animation-bake packed file"
            )
            return {"CANCELLED"}

        if img.depth != 32:
            bpy.ops.xplane.msg(
                "INVOKE_DEFAULT",
                msg_text="Bake image must be a PNG with an alpha channel"
            )
            return {"CANCELLED"}
        # ---------------------------------------------------------------------

        def select_objects(wiper: xplane_props.XPlaneWiperSettings) -> None:
            """Select Wiper Object (already guaranteed to exist) then Windshield"""
            for obj in context.selected_objects:
                obj.select_set(False)
            object_datablock = bpy.data.objects[wiper.object_name]
            object_datablock.select_set(True)
            windshield.select_set(True)
            context.view_layer.objects.active = windshield

        original_active_object = context.active_object
        original_frame = scene.frame_current
        original_bake_settings = {
            attr: getattr(scene.render.bake, attr)
            for attr in ("margin", "use_clear", "use_selected_to_active")
        }
        # Since Blender 5.0, Cycles only bakes to an image node that is active *and* selected
        original_bake_node_select = bake_node.select
        bake_temp_folder = img_filepath.parent / Path("_tmp_bake_images")
        bake_temp_folder.mkdir(parents=True, exist_ok=True)
        try:
            scene.render.bake.margin = 0
            scene.render.bake.use_clear = True
            scene.render.bake.use_selected_to_active = True
            bake_node.select = True
            paths = []
            for slot, wiper in enumerate(wipers, start=1):
                if not self.debug_slots[slot - 1]:
                    continue
                select_objects(wiper)

                print(
                    "Animated baking for frames (%d - %d)"
                    % (self.start, self.start + 255)
                )

                for cfra in range(self.start, self.start + 255):
                    assert (
                        1 <= cfra <= 255 * 4
                    ), f"Start is {self.start}, cfra is {cfra}"
                    bake_start = time.perf_counter()
                    print("Baking frame %d" % cfra)

                    # update scene to new frame and bake to template image
                    scene.frame_set(cfra)
                    new_img_filepath = bake_temp_folder / Path(
                        f"{img_filepath.stem}_slot{slot}_{cfra:03}.png"
                    )

                    if not self.debug_reuse_temps or (
                        self.debug_reuse_temps and not new_img_filepath.exists()
                    ):
                        ret = bpy.ops.object.bake(type=scene.cycles.bake_type)
                    else:
                        ret = {}

                    if "CANCELLED" in ret:
                        return {"CANCELLED"}
                    print("Bake time:", time.perf_counter() - bake_start)

                    # Currently the api has no img.save_as()
                    orig = img.filepath_raw
                    # !!! IMPORTANT! You must use filepath_raw! !!!
                    img.filepath_raw = str(new_img_filepath)
                    paths.append(Path(img.filepath_raw))
                    if not self.debug_reuse_temps:
                        img.save()
                        print("Saved %r" % new_img_filepath)
                    img.filepath_raw = orig
                print("Baking done!")

            try:
                if self.debug_master_filepath:
                    master_filepath = Path(
                        bpy.path.abspath(self.debug_master_filepath)
                    )
                else:
                    master_filepath = img_filepath.parent / Path(
                        "wiper_gradient_texture.png"
                    )
                xplane_wiper_gradient.make_wiper_images(
                    paths, *img.size, master_filepath
                )
            except OSError as e:
                bpy.ops.xplane.msg("INVOKE_DEFAULT", msg_text=str(e))
                return {"CANCELLED"}
            else:
                rain.wiper_texture = bpy.path.relpath(str(master_filepath)).replace(
                    "\\", "/"
                )
        finally:
            if not self.debug_reuse_temps:
                shutil.rmtree(bake_temp_folder, ignore_errors=True)

            for obj in context.selected_objects:
                obj.select_set(False)
            context.view_layer.objects.active = original_active_object
            scene.frame_set(original_frame)
            for attr, value in original_bake_settings.items():
                setattr(scene.render.bake, attr, value)
            bake_node.select = original_bake_node_select
        return {"FINISHED"}


register, unregister = bpy.utils.register_classes_factory((XPLANE_OT_bake_wiper_gradient_texture,))
