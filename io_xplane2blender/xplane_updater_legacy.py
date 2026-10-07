"""
The steps that brought files from older versions of XPlane2Blender up to date, run by xplane_updater
for files saved before each step's version. Settings that no longer exist are read and written as the
raw values Blender keeps in the file.
"""

import collections
import itertools
import re
from typing import Any, Dict, List, Union

import bpy

from io_xplane2blender import xplane_constants, xplane_helpers, xplane_props
from io_xplane2blender.xplane_helpers import XPlaneLogger
from io_xplane2blender.xplane_utils import xplane_updater_helpers


def layers_to_collection(logger: xplane_helpers.XPlaneLogger) -> None:
    """
    Side Effects: Collections may be created, properties changed; Deletes scene.xplane.layers

    - Renames all collections to the familiar and unambiguious "Layer N"
    - Copies any XPLaneLayers from scene.xplane.layers
    - Creates Collections for non-default XPlaneLayers w/o content
    - Sets visibility and exportablity
    - and finally deletes scene.xplane.layers
    """
    # --- Copy Layers to Collections ---------------------------------------
    def prepare_collections_for_renaming():
        for coll in bpy.data.collections:
            full_match = re.fullmatch(r"Collection(\.\d{3}|$)", coll.name)
            if full_match:
                coll.name = f"Collection 1{full_match.group(1)}"

            # Making this regular with the rest is better,
            # we're just going to replace all this anyway
            if "." not in coll.name:
                coll.name += ".000"

    prepare_collections_for_renaming()
    for i, scene in enumerate(bpy.data.scenes):
        if "layers" in scene.xplane and not scene.xplane["layers"]:
            for j, coll in enumerate(scene.collection.children, start=1):
                coll.name = f"Layer {j}" if i == 0 else f"Layer {j}_{scene.name}"
        elif "layers" in scene.xplane:
            # We rename everything from Collection {number} to Layer {number}_{scene.name}
            # 1. Correct any named "Collection$" to "Collection 1.000" (why Blender?!),
            #    keeping any trailing evidence of a name collision (.001, .002, etc)
            # 2. If our scene has a collection pre-made for the layer*, great! Use that!
            #    If our scene has a layer with non-default values but Blender didn't
            #    make a Collection for us (no Blender Data on it), make one ourselves
            #    Otherwise, go to the next layer
            #
            #    * We need to actually check every Collection N, Collection N.001 incase
            #      a previous scene didn't make that collection and Blender hasn't needed to
            #      make it unique by appending the .000 business
            # 3. Rename to match the pattern,
            #    copy the XPlaneLayer from scene.xplane.layers to coll.xplane.layer
            for layer in scene.xplane["layers"]:
                assert (
                    layer["index"] != -1
                ), f"XPlaneLayer f{layer.name} was never actually initialized in 2.79"
                collection_new_name = f"Layer {layer['index'] + 1}" + (
                    f"_{scene.name}" if i else f""
                )
                for suffix in (f"{j:03}" for j in range(0, i + 1)):
                    try_this = f"Collection {layer['index'] + 1}.{suffix}"
                    try:
                        coll = scene.collection.children[try_this]
                    except KeyError:
                        continue
                    else:
                        coll.name = collection_new_name
                        # 0 used to mean "layers" (default), 1 used to mean "root_objects"
                        coll.xplane.is_exportable_collection = (
                            not coll.hide_viewport
                            if scene.xplane.get("exportMode", 0) == 0
                            else False
                        )
                        scene.view_layers[0].layer_collection.children[
                            coll.name
                        ].hide_viewport = coll.hide_viewport  # Change eyeball
                        coll.hide_viewport = False
                    break
                else:  # no break, no matching collection found

                    def flatten(items: Dict[str, Any]):
                        """
                        Returns all the real values (except 'index') used in 'layer'
                        """
                        output = []

                        def f(item):
                            # No, it isn't perfect. I'm just sick of this API
                            if item == [] or item == dict():
                                return
                            if isinstance(item, list):
                                for v in item:
                                    f(v)
                            elif isinstance(item, dict):
                                for k, v in item.items():
                                    # - index will always be not None,
                                    # - expanded isn't impressive enough to matter
                                    # - no point collecting a change of "" for name, common mistake
                                    if (k not in {"expanded", "index"}) and (k, v) != (
                                        "name",
                                        "",
                                    ):
                                        f(v)
                            else:
                                output.append(item)

                        f(items)
                        return output

                    nondefaults = flatten(layer.to_dict())
                    if nondefaults:
                        coll = bpy.data.collections.new(collection_new_name)
                        scene.collection.children.link(coll)
                        coll.xplane.is_exportable_collection = False
                        scene.view_layers[0].layer_collection.children[
                            coll.name
                        ].hide_viewport = True
                        coll.hide_viewport = False
                    else:
                        continue

                def copy_layer_idprop_to_property(coll: bpy.types.Collection):
                    try:
                        coll.xplane["layer"]
                    except KeyError:
                        coll.xplane["layer"] = {}
                    finally:
                        coll.xplane["layer"].update(layer)

                copy_layer_idprop_to_property(coll)
        xplane_updater_helpers.delete_property_from_datablock(scene.xplane, "layers")


def change_pre_3_3_0_properties(logger: xplane_helpers.XPlaneLogger) -> None:
    """
    Side Effects: layer.exportType may change
    The purpose of this is (I think) to get pre 3_3_0 files up to speed.
    Or something.
    """
    for scene in bpy.data.scenes:
        for layer in [coll.xplane.layer for coll in scene.collection.children]:
            # set export mode to cockpit, if cockpit was previously enabled
            prev_export_type = layer.export_type
            if layer.get("cockpit"):
                layer.export_type = "cockpit"
                logger.info(
                    'Changed layer "%s"\'s Export Type from "%s" to "%s"'
                    % (layer.name, prev_export_type, layer.export_type)
                )
            else:
                layer.export_type = "aircraft"

    logger.info(
        "Unless otherwise noted, changed every layer's Export Type to 'Aircraft'"
    )


def update_LocRot(
    has_datarefs: Union[bpy.types.Object, bpy.types.Bone], logger: XPlaneLogger
) -> None:
    """
    Side Effects: has_datarefs/bone's datarefs' anim_type may change
    from Loc/Rot/LocRot->Transform

    Loc and Rot and LocRot options were combined in the enum,
    and the enum needed to be adjusted
    """

    # Recreate the pre_34 animation types enum
    ANIM_TYPE_TRANSLATE = "translate"
    ANIM_TYPE_ROTATE = "rotate"

    # fmt: off
    conversion_table = [
            #pre_34_anim_types  : post_34_anim_types
            (xplane_constants.ANIM_TYPE_TRANSFORM, xplane_constants.ANIM_TYPE_TRANSFORM),
            (                 ANIM_TYPE_TRANSLATE, xplane_constants.ANIM_TYPE_TRANSFORM),
            (                 ANIM_TYPE_ROTATE,    xplane_constants.ANIM_TYPE_TRANSFORM),
            (xplane_constants.ANIM_TYPE_SHOW,      xplane_constants.ANIM_TYPE_SHOW),
            (xplane_constants.ANIM_TYPE_HIDE,      xplane_constants.ANIM_TYPE_HIDE)
        ]
    # fmt: on

    # Returned string is the new enum_type to be used and assaigned
    def convert_old_to_new(old_anim_type: int) -> str:
        if old_anim_type >= 0 and old_anim_type < len(conversion_table):
            return conversion_table[old_anim_type][1]
        else:
            msg = "%s was not found in conversion table" % old_anim_type
            logger.error(msg)
            raise Exception(msg)

    for d in has_datarefs.xplane.datarefs:
        old_anim_type = d.get("anim_type")
        if old_anim_type is None:
            old_anim_type = 0  # If anim_type was never set in the first place, it's value is the default, aka 0 for the old anim_type

        new_anim_type = convert_old_to_new(old_anim_type)
        d.anim_type = new_anim_type
        logger.info(
            "Updated %s's animation dataref (%s)'s animation type from %s to %s"
            % (
                has_datarefs.name,
                d.path,
                conversion_table[old_anim_type][0].capitalize(),
                new_anim_type.capitalize(),
            )
        )


def rollback_blend_glass(logger: XPlaneLogger) -> None:
    """
    Side Effects: mat.xplane.blend_glass may change, mat.xplane.blend_v1100 deleted

    There was a mistake in creating Blend Glass as a member of blend_v1100,
    instead of as a BoolProperty.

    This saves Blend Glass (if needed) before blend_v1100 is deleted
    """
    for mat in bpy.data.materials:
        v10 = mat.xplane.get("blend_v1000")
        v11 = mat.xplane.get("blend_v1100")

        if v11 == 3:  # Aka, where BLEND_GLASS was in the enum
            # v4.1.0 note - we've moved blend_glass to the header
            # but I don't want to change the rest of this function
            # So... we fake it to match later expectations!
            mat.xplane["blend_glass"] = True

            # This bit of code reachs around Blender's magic EnumProperty
            # stuff and get at the RNA behind it, all to find the name.
            # If the default for blend_v1000 ever changes, we'll be covered.
            blend_v1000 = xplane_props.XPlaneMaterialSettings.bl_rna.properties[
                "blend_v1000"
            ]
            enum_items = blend_v1000.enum_items

            if v10 is None:
                v10_mode = enum_items[enum_items.find(blend_v1000.default)].name
            else:
                v10_mode = enum_items[v10].name
            logger.info(
                'Set material "{name}"\'s Blend Glass property to true and its Blend Mode to {v10_mode}'.format(
                    name=mat.name, v10_mode=v10_mode
                )
            )

        xplane_updater_helpers.delete_property_from_datablock(mat.xplane, "blend_v1100")


def set_shadow_local_and_delete_global_shadow(
    logger: xplane_helpers.XPlaneLogger,
) -> None:
    """
    Side Effects: mat.xplane.shadow_local may be set, based on the value of the root's
    global shadow if that mat was used in that root, layer.shadow is deleted

    To implement ATTR_shadow we needed material level shadow control, and if that was
    the case, we could use that to make the "uniform shadow->promote to GLOBAL_shadow"
    rule we like. We wanted to preserve people's shadow choice as best as possible,
    however, so this was used to populate people material's cast_local
    """

    # This helps us conveniently save the Cast shadow value for later after we delete it
    UsedLayerInfo = collections.namedtuple(
        "UsedLayerInfo", ["options", "cast_shadow", "final_name"]
    )

    def _update_potential_materials(
        potential_materials: List[bpy.types.Material], layer_options: "xplane_props.XPlaneLayer"
    ) -> None:
        for mat in potential_materials:
            # Default for shadow was True. get can't find shadow == no explicit value give
            val = bool(layer_options.get("shadow", True))
            mat.xplane.shadow_local = val  # Easy case #1

    def _print_error_table(
        material_uses: Dict[bpy.types.Material, List[UsedLayerInfo]]
    ) -> None:
        error_count = len(logger.findErrors())
        for mat, layers_used_in in material_uses.items():
            if len(layers_used_in) > 1 and any(
                layers_used_in[0].cast_shadow != l.cast_shadow for l in layers_used_in
            ):  # Checks for mixed use of Cast Shadow (Global)
                pad = max([len(final_name) for _, _, final_name in layers_used_in])
                logger.error(
                    "\n".join(
                        [
                            "Material '{}' is used across OBJs with different 'Cast Shadow (Global)' values:".format(
                                mat.name
                            ),
                            "Ambiguous OBJs".ljust(pad) + "| Cast Shadow (Global)",
                            "-" * pad + "|---------------------",
                            "\n".join(
                                "{}| {}".format(
                                    final_name.ljust(pad),
                                    "On" if cast_shadow else "Off",
                                )
                                for options, cast_shadow, final_name in layers_used_in
                            ),
                            "",
                        ]
                    )
                )
        if len(logger.findErrors()) > error_count:
            logger.info(
                "'Cast shadows' has been replaced by the Material's 'Cast Shadows (Local)'."
                " The above OBJs may have incorrect shadows unless 'Cast Shadows (Local)'"
                " is manually made uniform again, which could involve making"
                " duplicate materials for each OBJ"
            )

    # This way we'll be able to map the usage (and shared-ness) of a material
    material_uses = collections.defaultdict(
        list
    )  # type: Dict[bpy.types.Material, List[UsedLayerInfo]]

    for scene in bpy.data.scenes:
        for exportable_root in xplane_helpers.get_exportable_roots_in_scene(
            scene, scene.view_layers[0]
        ):  # Don't worry, we'll always have only 1 view layer
            layer_options = exportable_root.xplane.layer
            if layer_options.export_type in {
                xplane_constants.EXPORT_TYPE_AIRCRAFT,
                xplane_constants.EXPORT_TYPE_COCKPIT,
            }:
                layer_options["shadow"] = True

            potential_objects = xplane_helpers.get_potential_objects_in_exportable_root(
                exportable_root
            )
            potential_materials = [
                slot.material
                for obj in potential_objects
                for slot in obj.material_slots
                if slot.material
            ]
            _update_potential_materials(potential_materials, layer_options)
            used_layer_info = UsedLayerInfo(
                options=layer_options,
                cast_shadow=bool(layer_options.get("shadow", True)),
                final_name=layer_options.name
                if layer_options.name
                else exportable_root.name,
            )
            xplane_updater_helpers.delete_property_from_datablock(
                layer_options, "shadow"
            )
            for mat in potential_materials:
                material_uses[mat].append(used_layer_info)

    _print_error_table(material_uses)

    # They might not all be root objects, but all objects have a XPlaneLayer property group!
    for obj in bpy.data.objects:
        xplane_updater_helpers.delete_property_from_datablock(
            obj.xplane.layer, "shadow"
        )


def move_global_material_props(
    logger: xplane_helpers.XPlaneLogger,
):
    """
    Because it was deemed horribly annoying and bad semantics,
    NORMAL_METALNESS and BLEND_GLASS are
    going to be moved to the OBJ settings instead.

    Side Effects: The value of `Normal Metalness` and `Blend Glass`
    are copied to the OBJ settings with a very liberal dumb heuristic
    for solving ambiguities and defaults given. No old data is deleted.
    (Draped normal metalness and tint were for scenery, which is no longer made)

    On Accidental Re-run: Pre-v4.1.0-alpha.1 choices would be re-applied,
    overwriting new choices
    """
    default_blend_glass = False
    default_normal_metalness = False

    for scene in bpy.data.scenes:
        exp_collections = [
            col
            for col in xplane_helpers.get_collections_in_scene(scene)
            if col.xplane.is_exportable_collection
        ]
        exp_objects = [o for o in scene.objects if o.xplane.isExportableRoot]

        for exp in itertools.chain(exp_collections, exp_objects):

            if isinstance(exp, bpy.types.Collection):
                all_objects = exp.all_objects
            else:

                def recurse_obj_tree(obj: bpy.types.Collection):
                    yield obj
                    for c in obj.children:
                        yield from recurse_obj_tree(c)

                all_objects = [*recurse_obj_tree(exp)]

            exp.xplane.layer.blend_glass = default_blend_glass
            exp.xplane.layer.normal_metalness = default_normal_metalness

            for m in [
                slot.material
                for o in all_objects
                for slot in o.material_slots
                if slot.material
            ]:
                exp.xplane.layer.blend_glass |= bool(
                    m.xplane.get("blend_glass", default_blend_glass)
                )
                old_normal_metalness = bool(
                    m.xplane.get("normal_metalness", default_normal_metalness)
                )
                if not m.xplane.get("draped"):
                    exp.xplane.layer.normal_metalness |= old_normal_metalness


def panel_to_cockpit_feature(logger: xplane_helpers.XPlaneLogger):
    for mat in bpy.data.materials:
        mat.xplane.cockpit_feature = (
            xplane_constants.COCKPIT_FEATURE_PANEL
            if mat.xplane.get("panel", False)
            else xplane_constants.COCKPIT_FEATURE_NONE
        )


def regions_change_panel_mode(logger: xplane_helpers.XPlaneLogger):
    for col in bpy.data.collections:
        col.xplane.layer.cockpit_panel_mode = (
            xplane_constants.PANEL_COCKPIT_REGION
            if int(col.xplane.layer.cockpit_regions)
            else col.xplane.layer.cockpit_panel_mode
        )

def update_light_intensities(logger: xplane_helpers.XPlaneLogger):
    for light in bpy.data.lights:
        light_intensity = xplane_updater_helpers.delete_property_from_datablock(light.xplane, "param_intensity")
        
        if light_intensity != None:
            light.xplane.param_intensity_new = light_intensity
