import math
import os

import bpy
from mathutils import Vector

from io_xplane2blender import xplane_constants, xplane_display_sizes
from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import (
    TempFolder,
    obj_text,
    write_file,
    write_png,
)
from io_xplane2blender.tests.test_creation_helpers import create_initial_test_setup
from io_xplane2blender.xplane_importer.common import ImportOptions, ImportReport
from io_xplane2blender.xplane_importer.importing import import_obj_file
from io_xplane2blender.xplane_importer.obj_builder_parts import PartsBuilder

QUAD_VT = (
    "VT 0 0 0 0 1 0 0 0\nVT 0 0 -1 0 1 0 0 1\nVT 1 0 -1 0 1 0 1 1\nVT 1 0 0 0 1 0 1 0\n"
)
QUAD_IDX = "IDX10 0 1 2 0 2 3\n"
# A triangle a tenth of a meter wide, like a small knob
SMALL_VT = "VT\t0\t0\t0\t0\t1\t0\t0\t0\nVT\t0\t0\t-0.1\t0\t1\t0\t0\t1\nVT\t0.1\t0\t0\t0\t1\t0\t1\t0\n"
# The same needle on a dial that turns too: the dial holds it, so it is an Empty that stays
DIAL = "ANIM_begin\nANIM_rotate_begin 0 0 1 sim/dial\nANIM_rotate_key 0 0\nANIM_rotate_key 1 10\nANIM_rotate_end\n" + "ANIM_begin\nANIM_rotate_begin 1 0 0 sim/needle\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nTRIS 0 3\nANIM_end\nANIM_end\n"
NEEDLE = "ANIM_begin\nANIM_rotate_begin 1 0 0 sim/needle\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"


def loop_normals(mesh):
    if hasattr(mesh, "calc_normals_split"):
        mesh.calc_normals_split()
        return [tuple(loop.normal) for loop in mesh.loops]
    return [tuple(n.vector) for n in mesh.corner_normals]


class TestImportObj(XPlaneTestCase):
    def setUp(self) -> None:
        super().setUp()
        create_initial_test_setup()
        self.folder = TempFolder()
        self.report = ImportReport()
        self.png = write_png(self.folder.join("tex.png"))

    def tearDown(self) -> None:
        self.folder.cleanup()
        super().tearDown()

    def do_import(self, text: str, name: str = "thing.obj", **option_changes):
        path = write_file(self.folder.join(name), text)
        options = ImportOptions(**option_changes)
        built = import_obj_file(path, options, self.report)
        self.assertIsNotNone(built, f"import failed: {self.report.errors}")
        return built

    def meshes(self, built):
        return [o for o in built.objects if o.type == "MESH"]

    def empties(self, built):
        return [o for o in built.objects if o.type == "EMPTY"]

    # ---- geometry --------------------------------------------------------------------------
    def test_triangle_geometry(self) -> None:
        built = self.do_import(obj_text("", header="TEXTURE tex.png\n"))
        (obj,) = self.meshes(built)
        mesh = obj.data
        self.assertEqual(len(mesh.polygons), 1)
        # X-Plane (x, y up, z back) -> Blender (x, y forward, z up)
        coords = sorted(tuple(round(c, 5) for c in v.co) for v in mesh.vertices)
        self.assertEqual(coords, [(0, 0, 0), (0, 1, 0), (1, 0, 0)])
        # Clockwise seen from above in X-Plane becomes counter-clockwise, facing up
        self.assertAlmostEqual(mesh.polygons[0].normal.z, 1.0, places=5)
        for normal in loop_normals(mesh):
            self.assertAlmostEqual(normal[2], 1.0, places=4)
        uvs = sorted(tuple(round(c, 5) for c in loop.uv) for loop in mesh.uv_layers[0].data)
        self.assertEqual(uvs, [(0, 0), (0, 1), (1, 0)])

    def test_vertices_are_welded(self) -> None:
        built = self.do_import(obj_text("", vertices=QUAD_VT, indices=QUAD_IDX, tris="TRIS 0 6\n"))
        (obj,) = self.meshes(built)
        self.assertEqual(len(obj.data.vertices), 4)
        self.assertEqual(len(obj.data.polygons), 2)

    def test_custom_normals_keep_their_direction(self) -> None:
        vt = "VT 0 0 0 1 0 0 0 0\nVT 0 0 -1 0 0 -1 0 1\nVT 1 0 0 0 1 0 1 0\n"
        built = self.do_import(obj_text("", vertices=vt))
        (obj,) = self.meshes(built)
        seen = {tuple(round(c, 3) for c in n) for n in loop_normals(obj.data)}
        # X-Plane (1,0,0), (0,0,-1), (0,1,0) are Blender (1,0,0), (0,1,0), (0,0,1)
        self.assertEqual(seen, {(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)})

    def test_scale_option(self) -> None:
        built = self.do_import(obj_text(""), scale=2.0)
        (obj,) = self.meshes(built)
        self.assertAlmostEqual(max(v.co.x for v in obj.data.vertices), 2.0, places=5)

    def test_broken_indices_do_not_stop_the_import(self) -> None:
        built = self.do_import(obj_text("", indices="IDX10 0 1 2 0 1 99 5 6\n", tris="TRIS 0 8\n"))
        (obj,) = self.meshes(built)
        self.assertEqual(len(obj.data.polygons), 1)

    def test_degenerate_triangles_are_dropped(self) -> None:
        built = self.do_import(obj_text("", indices="IDX10 0 0 1 0 1 2\n", tris="TRIS 0 6\n"))
        (obj,) = self.meshes(built)
        self.assertEqual(len(obj.data.polygons), 1)

    # ---- materials -------------------------------------------------------------------------
    def image_nodes(self, material):
        return [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeTexImage"]

    def test_material_has_the_texture(self) -> None:
        built = self.do_import(obj_text("", header="TEXTURE tex.png\n"))
        material = self.meshes(built)[0].data.materials[0]
        (node,) = self.image_nodes(material)
        self.assertEqual(os.path.normpath(bpy.path.abspath(node.image.filepath)), os.path.normpath(self.png))

    def test_missing_texture_is_a_warning(self) -> None:
        self.do_import(obj_text("", header="TEXTURE nothere.png\n"))
        self.assertTrue(any("nothere.png" in w for w in self.report.warnings))

    def test_texture_found_in_another_case_and_format(self) -> None:
        write_png(self.folder.join("sub", "Paint.PNG"))
        built = self.do_import(obj_text("", header="TEXTURE sub/paint.png\n"))
        (node,) = self.image_nodes(self.meshes(built)[0].data.materials[0])
        self.assertTrue(node.image.filepath.lower().endswith("paint.png"))
        self.assertFalse(self.report.warnings)

    def test_materials_follow_the_attribute_state(self) -> None:
        body = "TRIS 0 3\nATTR_no_blend 0.4\nTRIS 0 3\nATTR_blend\nATTR_shiny_rat 0.8\nTRIS 0 3\nATTR_shiny_rat 0.8\nTRIS 0 3\n"
        built = self.do_import(obj_text(body, header="TEXTURE tex.png\n", tris=None))
        (obj,) = self.meshes(built)
        materials = list(obj.data.materials)
        self.assertEqual(len(materials), 3)
        self.assertEqual([p.material_index for p in obj.data.polygons], [0, 1, 2, 2])
        default, cutout, shiny = materials
        self.assertEqual(default.xplane.blend_v1000, xplane_constants.BLEND_ON)
        self.assertEqual(cutout.xplane.blend_v1000, xplane_constants.BLEND_OFF)
        self.assertAlmostEqual(cutout.xplane.blendRatio, 0.4, places=4)
        self.assertAlmostEqual(shiny.specular_intensity, 0.8, places=4)

    def test_alpha_cutoff_is_built_from_nodes(self) -> None:
        built = self.do_import(obj_text("ATTR_no_blend 0.3\nTRIS 0 3\n", header="TEXTURE tex.png\n", tris=None))
        material = self.meshes(built)[0].data.materials[0]
        math_nodes = [n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeMath" and n.operation == "GREATER_THAN"]
        self.assertEqual(len(math_nodes), 1)
        self.assertAlmostEqual(math_nodes[0].inputs[1].default_value, 0.3, places=4)

    def test_blended_materials_write_depth_in_eevee(self) -> None:
        # With either on, EEVEE sorts per object only and the triangles of one mesh show through each other
        built = self.do_import(obj_text("TRIS 0 3\n", header="TEXTURE tex.png\n", tris=None))
        material = self.meshes(built)[0].data.materials[0]
        self.assertFalse(material.show_transparent_back)
        if hasattr(material, "use_transparency_overlap"):
            self.assertFalse(material.use_transparency_overlap)

    def test_other_material_attributes(self) -> None:
        body = "ATTR_poly_os 2\nATTR_solid_camera\nATTR_no_shadow\nATTR_hard concrete\nTRIS 0 3\n"
        built = self.do_import(obj_text(body, tris=None))
        x = self.meshes(built)[0].data.materials[0].xplane
        self.assertEqual(x.poly_os, 2)
        self.assertTrue(x.solid_camera)
        self.assertFalse(x.shadow_local)
        self.assertEqual(x.surfaceType, xplane_constants.SURFACE_TYPE_CONCRETE)
        self.assertFalse(x.deck)

    def test_attributes_without_a_setting_become_custom_attributes(self) -> None:
        built = self.do_import(obj_text("ATTR_layer_group objects 1\nTRIS 0 3\n", tris=None))
        attributes = self.meshes(built)[0].data.materials[0].xplane.customAttributes
        self.assertEqual([(a.name, a.value) for a in attributes], [("ATTR_layer_group", "objects 1")])

    def test_not_drawn_meshes_are_wire_and_not_rendered(self) -> None:
        built = self.do_import(obj_text("ATTR_draw_disable\nTRIS 0 3\n", tris=None))
        (obj,) = self.meshes(built)
        self.assertFalse(obj.data.materials[0].xplane.draw)
        self.assertEqual(obj.display_type, "WIRE")
        self.assertTrue(obj.hide_render)

    def test_normal_metalness_blue_is_reflectance(self) -> None:
        # LR's Substance preset writes F0 to the blue channel. X-Plane treats 0 to 0.08 as dielectric
        # (the specular level) and anything above as metalness
        write_png(self.folder.join("tex_NRM.png"))
        header = "TEXTURE tex.png\nTEXTURE_NORMAL tex_NRM.png\nNORMAL_METALNESS\nGLOBAL_specular 1\n"
        material = self.meshes(self.do_import(obj_text("", header=header)))[0].data.materials[0]
        bsdf = next(n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        metallic = bsdf.inputs["Metallic"].links[0].from_node
        self.assertEqual(metallic.bl_idname, "ShaderNodeMapRange")
        self.assertAlmostEqual(metallic.inputs["From Min"].default_value, 0.08)
        specular = bsdf.inputs.get("Specular IOR Level") or bsdf.inputs["Specular"]
        divide = specular.links[0].from_node
        self.assertEqual(divide.operation, "DIVIDE")
        self.assertEqual(divide.inputs[0].links[0].from_node.operation, "MINIMUM")

    def test_material_map_red_is_reflectance(self) -> None:
        # XP12 (A330 style): TEXTURE_MAP material_gloss has F0 in red and gloss in green
        write_png(self.folder.join("tex_MAT.png"))
        header = "TEXTURE tex.png\nTEXTURE_MAP material_gloss tex_MAT.png\nNORMAL_METALNESS\n"
        material = self.meshes(self.do_import(obj_text("", header=header)))[0].data.materials[0]
        bsdf = next(n for n in material.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
        self.assertEqual(bsdf.inputs["Metallic"].links[0].from_node.bl_idname, "ShaderNodeMapRange")
        self.assertTrue(bsdf.inputs["Roughness"].links)

    def test_global_specular_is_the_default_shininess(self) -> None:
        built = self.do_import(obj_text("", header="GLOBAL_specular 0.6\n"))
        self.assertAlmostEqual(self.meshes(built)[0].data.materials[0].specular_intensity, 0.6, places=4)

    def test_materials_can_be_skipped(self) -> None:
        built = self.do_import(obj_text("", header="TEXTURE tex.png\n"), import_materials=False)
        material = self.meshes(built)[0].data.materials[0]
        self.assertFalse(material.use_nodes and self.image_nodes(material))

    # ---- export setup ----------------------------------------------------------------------
    def test_collection_can_be_an_export_root(self) -> None:
        built = self.do_import(
            obj_text("", header="TEXTURE tex.png\nBLEND_GLASS\nGLOBAL_cockpit_lit\nGLOBAL_no_shadow\n"), name="my_part.obj", make_exportable=True
        )
        collection = built.collection
        self.assertEqual(collection.name, "my_part")
        self.assertTrue(collection.xplane.is_exportable_collection)
        layer = collection.xplane.layer
        self.assertEqual(layer.name, "my_part")
        self.assertEqual(os.path.normpath(layer.texture), os.path.normpath(self.png))
        self.assertTrue(layer.blend_glass)
        self.assertEqual([(a.name) for a in layer.customAttributes], ["GLOBAL_no_shadow"])
        self.assertEqual(layer.export_type, xplane_constants.EXPORT_TYPE_AIRCRAFT)
        self.assertTrue(bpy.context.scene.xplane.optimize)

    def test_collections_are_not_export_roots_unless_asked(self) -> None:
        built = self.do_import(obj_text("", header="TEXTURE tex.png\n"))
        self.assertFalse(built.collection.xplane.is_exportable_collection)
        # The settings are filled in anyway, so ticking "Root Collection" later is all it takes
        self.assertEqual(os.path.normpath(built.collection.xplane.layer.texture), os.path.normpath(self.png))

    def test_manipulators_make_it_a_cockpit_object(self) -> None:
        built = self.do_import(obj_text("ATTR_manip_command button sim/x tip\nTRIS 0 3\n", tris=None))
        self.assertEqual(built.collection.xplane.layer.export_type, xplane_constants.EXPORT_TYPE_COCKPIT)

    # ---- manipulators and light level ---------------------------------------------------
    def test_command_manipulator(self) -> None:
        built = self.do_import(obj_text("ATTR_manip_command button sim/lights/beacon_lights_toggle Toggle the beacon\nTRIS 0 3\n", tris=None))
        (obj,) = self.meshes(built)
        m = obj.xplane.manip
        self.assertTrue(m.enabled)
        self.assertEqual(m.type, xplane_constants.MANIP_COMMAND)
        self.assertEqual(m.cursor, xplane_constants.MANIP_CURSOR_BUTTON)
        self.assertEqual(m.command, "sim/lights/beacon_lights_toggle")
        self.assertEqual(m.tooltip, "Toggle the beacon")
        self.assertEqual(obj.name, "Toggle the beacon")
        self.assertEqual(self.report.manipulators_imported, 1)

    def test_manipulators_with_values(self) -> None:
        body = (
            "ATTR_manip_drag_xy hand 0.1 0.2 0 1 5 6 sim/a sim/b Drag it\nTRIS 0 3\n"
            "ATTR_manip_command_knob rotate_medium sim/up sim/down Turn\nTRIS 0 3\n"
            "ATTR_manip_toggle button 2 3 sim/t Flip\nTRIS 0 3\n"
        )
        built = self.do_import(obj_text(body, tris=None))
        by_name = {o.name: o.xplane.manip for o in self.meshes(built)}
        drag = by_name["Drag it"]
        self.assertEqual(drag.type, xplane_constants.MANIP_DRAG_XY)
        self.assertAlmostEqual(drag.dx, 0.1, places=4)
        self.assertAlmostEqual(drag.v2_max, 6.0, places=4)
        self.assertEqual((drag.dataref1, drag.dataref2), ("sim/a", "sim/b"))
        knob = by_name["Turn"]
        self.assertEqual((knob.positive_command, knob.negative_command), ("sim/up", "sim/down"))
        toggle = by_name["Flip"]
        self.assertEqual((toggle.v_on, toggle.v_off, toggle.dataref1), (2.0, 3.0, "sim/t"))

    def test_manipulator_wheel_and_detents(self) -> None:
        body = "ATTR_manip_drag_axis hand 0 1 0 0 1 sim/d Slide\nATTR_manip_wheel 0.25\nATTR_axis_detent_range 0 0.5 0.1\nTRIS 0 3\n"
        built = self.do_import(obj_text(body, tris=None))
        m = self.meshes(built)[0].xplane.manip
        self.assertAlmostEqual(m.wheel_delta, 0.25, places=4)
        self.assertEqual([(r.start, r.end) for r in m.axis_detent_ranges], [(0.0, 0.5)])

    def test_manipulators_can_be_skipped(self) -> None:
        built = self.do_import(obj_text("ATTR_manip_command button sim/x tip\nTRIS 0 3\n", tris=None), import_manipulators=False)
        self.assertFalse(self.meshes(built)[0].xplane.manip.enabled)

    def test_objects_split_by_manipulator_and_light_level(self) -> None:
        body = (
            "ATTR_light_level 0 1 sim/lit\nTRIS 0 3\nATTR_light_level_reset\nTRIS 0 3\n"
            "ATTR_manip_command button sim/x A\nTRIS 0 3\nATTR_manip_command button sim/y B\nTRIS 0 3\n"
        )
        built = self.do_import(obj_text(body, tris=None))
        meshes = self.meshes(built)
        self.assertEqual(len(meshes), 4)
        lit = [o for o in meshes if o.xplane.lightLevel]
        self.assertEqual(len(lit), 1)
        self.assertEqual(lit[0].xplane.lightLevel_dataref, "sim/lit")
        self.assertEqual((lit[0].xplane.lightLevel_v1, lit[0].xplane.lightLevel_v2), (0.0, 1.0))

    # ---- animations ------------------------------------------------------------------------
    def test_static_anim_blocks_move_the_mesh(self) -> None:
        body = "ANIM_begin\nANIM_trans 5 0 0 5 0 0\nANIM_rotate 0 1 0 90 90\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (obj,) = self.meshes(built)
        self.assertFalse(self.empties(built))  # nothing animates, so no Empty is needed
        self.assertEqual(obj.matrix_basis.to_translation()[:], (5.0, 0.0, 0.0))
        # A turn of 90 degrees about X-Plane's up axis is the same turn about Blender's Z
        self.assertAlmostEqual(obj.matrix_basis.to_euler().z, math.radians(90), places=4)

    def frame_values(self, obj, data_path: str, index: int):
        from io_xplane2blender.xplane_helpers import get_action_fcurves

        (fcurve,) = [f for f in get_action_fcurves(obj) if f.data_path == data_path and f.array_index == index]
        return [(round(k.co[0]), round(k.co[1], 4), k.interpolation) for k in fcurve.keyframe_points]

    def test_rotation_animation(self) -> None:
        body = (
            "ANIM_begin\nANIM_trans 1 2 3 1 2 3\nANIM_rotate_begin 1 0 0 sim/gauge/needle\n"
            "ANIM_rotate_key 0 0\nANIM_rotate_key 10 90\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        )
        built = self.do_import(obj_text(body, tris=None))
        # The part carries its own animation, with its pivot as its origin
        self.assertFalse(self.empties(built))
        (mesh,) = self.meshes(built)
        empty = mesh
        self.assertEqual([(d.path, d.anim_type) for d in empty.xplane.datarefs], [("sim/gauge/needle", xplane_constants.ANIM_TYPE_TRANSFORM)])
        self.assertEqual(self.frame_values(empty, 'xplane.datarefs[0].value', 0), [(1, 0.0, "LINEAR"), (2, 10.0, "LINEAR")])
        # X-Plane's x axis is Blender's, the static translation is kept on the object
        self.assertEqual(empty.location[:], (1.0, -3.0, 2.0))
        self.assertEqual(self.frame_values(empty, "rotation_euler", 0), [(1, 0.0, "LINEAR"), (2, round(math.radians(90), 4), "LINEAR")])
        self.assertEqual(self.report.animations_imported, 1)

    def test_translation_animation_keeps_the_static_offset(self) -> None:
        body = "ANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_trans_begin sim/slide\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0 1 0\nANIM_trans_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (empty,) = self.meshes(built)
        # X-Plane's y (up) is Blender's z: 1 up plus the animated 1 up
        self.assertEqual(self.frame_values(empty, "location", 2), [(1, 1.0, "LINEAR"), (2, 2.0, "LINEAR")])

    def test_the_scene_opens_in_the_parked_pose(self) -> None:
        # Keys at -1, 0 and 1: the key nearest the default value 0 is on frame 1
        body = "ANIM_begin\nANIM_rotate_begin 0 1 0 sim/surface\nANIM_rotate_key -1 -20\nANIM_rotate_key 0 0\nANIM_rotate_key 1 20\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (empty,) = self.meshes(built)
        self.assertEqual([f for f, _, _ in self.frame_values(empty, "rotation_euler", 2)], [0, 1, 2])
        bpy.context.scene.frame_set(1)
        self.assertAlmostEqual(empty.rotation_euler.z, 0.0, places=5)
        bpy.context.view_layer.update()
        self.assertAlmostEqual(self.meshes(built)[0].matrix_world.to_euler().z, 0.0, places=5)

    def test_landing_gear_defaults_to_down(self) -> None:
        body = "ANIM_begin\nANIM_trans_begin sim/flightmodel2/gear/deploy_ratio[0]\nANIM_trans_key 0 0 1 0\nANIM_trans_key 1 0 0 0\nANIM_trans_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (empty,) = self.meshes(built)
        bpy.context.scene.frame_set(1)
        self.assertAlmostEqual(empty.location.z, 0.0, places=5)  # the key for deploy ratio 1

    def test_non_axis_rotation_uses_axis_angle(self) -> None:
        body = "ANIM_begin\nANIM_rotate_begin 1 1 0 sim/x\nANIM_rotate_key 0 0\nANIM_rotate_key 1 60\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (empty,) = self.meshes(built)
        self.assertEqual(empty.rotation_mode, "AXIS_ANGLE")
        bpy.context.scene.frame_set(2)
        self.assertAlmostEqual(empty.rotation_axis_angle[0], math.radians(60), places=4)

    def test_a_turn_before_a_rotation_goes_into_the_part(self) -> None:
        body = "ANIM_begin\nANIM_rotate 0 1 0 45 45\nANIM_rotate_begin 1 0 0 sim/x\nANIM_rotate_key 0 0\nANIM_rotate_key 1 10\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        self.assertFalse(self.empties(built))
        (part,) = self.meshes(built)
        self.assertEqual(len(part.xplane.datarefs), 1)

    def test_parts_that_share_a_turn_share_the_frame(self) -> None:
        part = "ANIM_begin\nANIM_trans %s 0 0 %s 0 0\nANIM_rotate 0 1 0 45 45\nANIM_rotate_begin 1 0 0 sim/%s\nANIM_rotate_key 0 0\nANIM_rotate_key 1 10\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(part % (1, 1, "a") + part % (2, 2, "b"), tris=None))
        (frame,) = self.empties(built)
        self.assertEqual([m.parent for m in self.meshes(built)], [frame, frame])
        # Each part is where it was: the frame turns, the part sits in the frame
        bpy.context.view_layer.update()
        self.assertEqual(sorted(round(m.matrix_world.translation.x, 4) for m in self.meshes(built)), [1.0, 2.0])

    def test_a_move_and_a_turn_of_one_dataref_make_one_object(self) -> None:
        body = (
            "ANIM_begin\nANIM_trans_begin sim/a\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0 1 0\nANIM_trans_end\n"
            "ANIM_rotate_begin 1 0 0 sim/a\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        )
        built = self.do_import(obj_text(body, tris=None))
        self.assertFalse(self.empties(built))
        (part,) = self.meshes(built)
        self.assertEqual(1, len(part.xplane.datarefs))
        self.assertEqual([(1, 0.0, "LINEAR"), (2, 1.0, "LINEAR")], self.frame_values(part, "location", 2))
        self.assertEqual([(1, 0.0, "LINEAR"), (2, round(math.radians(90), 4), "LINEAR")], self.frame_values(part, "rotation_euler", 0))

    def test_turns_about_three_axes_of_one_dataref_are_euler_angles_of_one_object(self) -> None:
        turn = "ANIM_rotate_begin %s sim/a\nANIM_rotate_key 0 0\nANIM_rotate_key 1 %s\nANIM_rotate_end\n"
        # X-Plane's y, x and z are Blender's Z, X and -Y, and the first is the outermost
        body = "ANIM_begin\n" + turn % ("0 1 0", 10) + turn % ("1 0 0", 20) + turn % ("0 0 1", 30) + "TRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        self.assertFalse(self.empties(built))
        (part,) = self.meshes(built)
        self.assertEqual("YXZ", part.rotation_mode)

    def test_turns_of_different_datarefs_need_an_object_each(self) -> None:
        turn = "ANIM_rotate_begin %s sim/%s\nANIM_rotate_key 0 0\nANIM_rotate_key 1 %s\nANIM_rotate_end\n"
        body = "ANIM_begin\n" + turn % ("0 1 0", "a", 10) + turn % ("1 0 0", "b", 20) + "TRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (empty,) = self.empties(built)
        (part,) = self.meshes(built)
        self.assertEqual(empty, part.parent)
        self.assertEqual(["sim/a"], [d.path for d in empty.xplane.datarefs])
        self.assertEqual(["sim/b"], [d.path for d in part.xplane.datarefs])

    def test_show_and_hide_and_a_move_are_on_the_part(self) -> None:
        body = "ANIM_begin\nANIM_show 1 2 sim/vis\n" + NEEDLE.replace("ANIM_begin\n", "", 1)
        built = self.do_import(obj_text(body, tris=None))
        self.assertFalse(self.empties(built))
        (part,) = self.meshes(built)
        self.assertEqual({"sim/vis", "sim/needle"}, {d.path for d in part.xplane.datarefs})

    def test_show_and_hide(self) -> None:
        body = (
            "ANIM_begin\nANIM_hide 0.5 1.5 sim/a\nTRIS 0 3\nANIM_end\n"
            "ANIM_begin\nANIM_show 0.5 1.5 sim/b\nTRIS 0 3\nANIM_end\n"
            "ANIM_begin\nANIM_show -0.5 0.5 sim/c\nTRIS 0 3\nANIM_end\n"
        )
        built = self.do_import(obj_text(body, tris=None))
        # A show or hide that holds one part is on the part
        self.assertFalse(self.empties(built))
        holders = {e.xplane.datarefs[0].path: e for e in self.meshes(built)}
        hide, show_out, show_in = holders["sim/a"], holders["sim/b"], holders["sim/c"]
        self.assertEqual((hide.xplane.datarefs[0].anim_type, hide.xplane.datarefs[0].show_hide_v1, hide.xplane.datarefs[0].show_hide_v2), (xplane_constants.ANIM_TYPE_HIDE, 0.5, 1.5))
        # At the default value 0, "hide 0.5..1.5" and "show -0.5..0.5" are visible, "show 0.5..1.5" is not
        self.assertFalse(hide.hide_viewport)
        self.assertTrue(show_out.hide_viewport)
        self.assertFalse(show_in.hide_viewport)
        self.assertTrue(show_out.hide_viewport and show_out.hide_render)

    def test_show_and_hide_before_the_first_block_cover_the_whole_file(self) -> None:
        body = "ANIM_hide 0.5 1.5 sim/whole\nTRIS 0 3\nANIM_begin\nANIM_trans 1 0 0 1 0 0\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        # One of the parts carries the line, the other is below it, so it is hidden with it
        self.assertFalse(self.empties(built))
        (carrier,) = [m for m in self.meshes(built) if m.xplane.datarefs]
        self.assertEqual(carrier.xplane.datarefs[0].anim_type, xplane_constants.ANIM_TYPE_HIDE)
        (other,) = [m for m in self.meshes(built) if m != carrier]
        self.assertEqual(other.parent, carrier)

    def test_parts_under_one_animation_hang_on_the_biggest_one(self) -> None:
        body = (
            "ANIM_begin\nANIM_rotate_begin 0 1 0 sim/knob\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\n"
            "TRIS 0 3\nATTR_light_level 0 1 sim/lit\nTRIS 0 3\nANIM_end\n"
        )
        built = self.do_import(obj_text(body, tris=None))
        self.assertFalse(self.empties(built))
        (carrier,) = [m for m in self.meshes(built) if m.xplane.datarefs]
        (other,) = [m for m in self.meshes(built) if m != carrier]
        self.assertEqual(other.parent, carrier)

    def test_a_lit_part_does_not_carry_the_animation_for_one_that_is_not(self) -> None:
        # The light level of a parent goes on to the children that have none, so the one without is the carrier
        spin = "ANIM_begin\nANIM_rotate_begin 0 1 0 sim/knob\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\n"
        built = self.do_import(obj_text(spin + "ATTR_light_level 0 1 sim/lit\nTRIS 0 3\nATTR_light_level_reset\nTRIS 0 3\nANIM_end\n", tris=None))
        self.assertFalse(self.empties(built))
        (carrier,) = [m for m in self.meshes(built) if m.xplane.datarefs]
        self.assertFalse(carrier.xplane.lightLevel)
        (lit,) = [m for m in self.meshes(built) if m != carrier]
        self.assertEqual(lit.parent, carrier)

    def test_parts_that_are_all_lit_can_hang_on_one_of_them(self) -> None:
        spin = "ANIM_begin\nANIM_rotate_begin 0 1 0 sim/knob\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\n"
        body = spin + "ATTR_light_level 0 1 sim/a\nTRIS 0 3\nATTR_light_level 0 1 sim/b\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        self.assertFalse(self.empties(built))

    def test_animations_with_nothing_in_them_are_left_out(self) -> None:
        body = "ANIM_begin\nANIM_trans_begin sim/x\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0 1 0\nANIM_trans_end\nANIM_end\nTRIS 0 3\n"
        built = self.do_import(obj_text(body, tris=None))
        self.assertEqual([], [o for o in built.objects if o.type == "EMPTY"])
        self.assertTrue(any("nothing in them" in text for text in self.report.infos))

    def test_a_decimal_comma_does_not_stop_the_import(self) -> None:
        body = "ATTR_manip_drag_axis hand 0 1 0 0,05 1 sim/d Slide\nATTR_manip_wheel 0,5\nTRIS 0 3\n"
        built = self.do_import(obj_text(body, tris=None))
        manip = self.meshes(built)[0].xplane.manip
        self.assertAlmostEqual(manip.v1, 0.05, places=4)
        self.assertAlmostEqual(manip.wheel_delta, 0.5, places=4)

    def test_hiding_can_be_turned_off(self) -> None:
        built = self.do_import(obj_text("ANIM_begin\nANIM_show 1 2 sim/b\nTRIS 0 3\nANIM_end\n", tris=None), hide_default_hidden=False)
        self.assertFalse(any(o.hide_viewport for o in built.objects))

    def test_animations_can_be_skipped(self) -> None:
        body = "ANIM_begin\nANIM_trans 1 0 0 1 0 0\nANIM_rotate_begin 1 0 0 sim/x\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nANIM_show 1 2 sim/y\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None), import_animations=False)
        self.assertFalse(self.empties(built))
        self.assertEqual(len(self.meshes(built)), 1)

    def test_keys_are_stored_in_ascending_order(self) -> None:
        body = "ANIM_begin\nANIM_rotate_begin 1 0 0 sim/x\nANIM_rotate_key 1 90\nANIM_rotate_key 0 0\nANIM_rotate_end\nTRIS 0 3\nANIM_end\n"
        built = self.do_import(obj_text(body, tris=None))
        (empty,) = self.meshes(built)
        self.assertEqual([v for _, v, _ in self.frame_values(empty, "xplane.datarefs[0].value", 0)], [0.0, 1.0])

    # ---- lights, magnets, emitters -----------------------------------------------------
    def test_lights(self) -> None:
        body = "LIGHT_NAMED beacon 1 2 3\nLIGHT_PARAM airplane_nav_left 4 5 6 0.5 1\nLIGHT_CUSTOM 0 0 0 1 0 0 0.5 3 0.1 0.2 0.3 0.4 sim/dr\n"
        built = self.do_import(obj_text(body, tris=None))
        lights = {o.name: o for o in built.objects if o.type == "LIGHT"}
        self.assertEqual(len(lights), 3)
        named = lights["beacon"]
        self.assertEqual(named.data.xplane.type, xplane_constants.LIGHT_NAMED)
        self.assertEqual(named.data.xplane.name, "beacon")
        self.assertEqual(tuple(round(c, 4) for c in named.location), (1.0, -3.0, 2.0))
        param = lights["airplane_nav_left"].data.xplane
        self.assertEqual((param.type, param.params), (xplane_constants.LIGHT_PARAM, "0.5 1"))
        custom = [l for l in lights.values() if l.data.xplane.type == xplane_constants.LIGHT_CUSTOM][0].data
        self.assertEqual(tuple(round(c, 3) for c in custom.color), (1.0, 0.0, 0.0))
        self.assertEqual(custom.xplane.dataref, "sim/dr")
        # The exporter writes the Blender power as the alpha, and the size and texture coordinates from the settings
        self.assertAlmostEqual(custom.energy, 0.5)
        self.assertAlmostEqual(custom.xplane.size, 3.0)
        self.assertEqual([round(v, 3) for v in custom.xplane.uv], [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(self.report.lights_imported, 3)

    def test_lights_take_their_color_from_their_parameters(self) -> None:
        body = "LIGHT_PARAM airplane_landing_pm 1 2 3 0.2 0.4 0.6 0 200000cd 0 0 -1 0.5\n"
        built = self.do_import(obj_text(body, tris=None))
        (light,) = [o for o in built.objects if o.type == "LIGHT"]
        self.assertEqual(tuple(round(c, 3) for c in light.data.color), (0.2, 0.4, 0.6))

    def light(self, body: str, **options):
        built = self.do_import(obj_text(body, tris=None), **options)
        (light,) = [o for o in built.objects if o.type == "LIGHT"]
        bpy.context.view_layer.update()
        return light

    def test_spill_lights_point_where_lights_txt_says(self) -> None:
        # airplane_generic_pm is a SPILL_SW: it lights its surroundings, with a half angle of 60 degrees here
        light = self.light("LIGHT_PARAM airplane_generic_pm 1 2 3 1 0.5 0 18 25cd 0 -1 0 0.5\n", light_strength=1.0)
        self.assertEqual(light.data.type, "SPOT")
        self.assertAlmostEqual(light.data.spot_size, math.radians(120), places=4)
        self.assertEqual(tuple(round(c, 3) for c in light.data.color), (1.0, 0.5, 0.0))
        down = light.matrix_world.to_3x3() @ Vector((0, 0, -1))  # X-Plane -Y is Blender -Z
        self.assertLess((down - Vector((0, 0, -1))).length, 1e-4)
        # 25 candela, and the exporter still writes the parameters as they were
        self.assertAlmostEqual(light.data.energy, 25 * 4 * math.pi**2 / 683, places=3)
        self.assertEqual(light.data.xplane.params, "1 0.5 0 18 25cd 0 -1 0 0.5")

    def test_a_lit_light_has_the_power_its_intensity_asks_for_and_says_how_much_it_was_multiplied(self) -> None:
        from io_xplane2blender import xplane_light_sync

        # 200000cd is more than the preview's own limit on a light's power: the link goes by the intensity
        text = "LIGHT_PARAM airplane_landing_pm 1 2 3 1 1 1 0 200000cd 0 -1 0 0.5\n"
        light = self.light(text, light_strength=2.0)
        self.assertAlmostEqual(200000 * 4 * math.pi**2 / 683 * 2.0, light.data.energy, places=1)
        self.assertEqual(2.0, light.data[xplane_light_sync.STRENGTH])
        self.assertEqual("1 1 1 0 200000cd 0 -1 0 0.5", light.data.xplane.params)
        # Nothing was pushed or pulled while it was built, and selecting it changes nothing
        bpy.context.view_layer.objects.active = light
        light.select_set(True)
        xplane_light_sync.blender_changed()
        self.assertEqual("1 1 1 0 200000cd 0 -1 0 0.5", light.data.xplane.params)

    def test_lights_that_are_off_have_no_strength_to_remember(self) -> None:
        from io_xplane2blender import xplane_light_sync

        light = self.light("LIGHT_PARAM airplane_landing_pm 1 2 3 1 1 1 0 20000cd 0 -1 0 0.5\n")
        self.assertEqual(0.0, light.data.energy)
        self.assertNotIn(xplane_light_sync.STRENGTH, light.data)

    def test_spill_lights_are_off_unless_asked(self) -> None:
        light = self.light("LIGHT_PARAM airplane_generic_pm 1 2 3 1 1 1 18 25cd 0 -1 0 0.5\n")
        self.assertEqual(light.data.energy, 0.0)
        self.assertGreater(light.data["xplane_watts_when_on"], 0.5)

    def test_billboards_do_not_light_the_scene(self) -> None:
        light = self.light("LIGHT_PARAM airplane_generic_bb 1 2 3 1 1 1 18 25cd 0 -1 0 0.5\n", light_strength=1.0)
        self.assertEqual(light.data.type, "POINT")
        self.assertEqual(light.data.energy, 0.0)
        for ray in ("visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter"):
            self.assertFalse(getattr(light, ray), ray)

    def test_custom_spill_lights_keep_their_settings(self) -> None:
        light = self.light("LIGHT_SPILL_CUSTOM 1 2 3 0.9 0.8 0.7 1 0.4 0 0 -1 0.5 my/dataref\n", light_strength=1.0)
        self.assertEqual(light.data.type, "SPOT")
        self.assertAlmostEqual(light.data.xplane.size, 0.4)
        self.assertEqual(light.data.xplane.dataref, "my/dataref")
        self.assertEqual(tuple(round(c, 3) for c in light.data.color), (0.9, 0.8, 0.7))
        self.assertGreater(light.data.energy, 0.0)
        # X-Plane -Z is the way the plane flies, and Blender +Y
        pointing = light.matrix_world.to_3x3() @ Vector((0, 0, -1))
        self.assertLess((pointing - Vector((0, 1, 0))).length, 1e-4)

    def test_colors_outside_the_color_picker_are_kept(self) -> None:
        light = self.light("LIGHT_CUSTOM 0 0 0 -1 0 -0.5 -2 3 0.5 0.5 1 1 sim/dr\n")
        self.assertTrue(light.data.xplane.enable_rgb_override)
        self.assertEqual([round(v, 3) for v in light.data.xplane.rgb_override_values], [-1.0, 0.0, -0.5])
        self.assertAlmostEqual(light.data.energy, -2.0)

    def test_omni_spill_lights_are_point_lights(self) -> None:
        light = self.light("LIGHT_SPILL_CUSTOM 0 0 0 1 1 1 1 2 0 0 0 1 none\n")
        self.assertEqual(light.data.type, "POINT")

    def test_a_spill_alpha_other_than_one_is_reported(self) -> None:
        self.light("LIGHT_SPILL_CUSTOM 0 0 0 1 1 1 0 2 0 0 0 1 none\n")
        self.assertTrue(any("alpha" in w for w in self.report.warnings), self.report.warnings)

    def test_lights_can_be_skipped(self) -> None:
        built = self.do_import(obj_text("LIGHT_NAMED beacon 1 2 3\n"), import_lights=False)
        self.assertFalse([o for o in built.objects if o.type == "LIGHT"])

    def test_lights_in_hidden_blocks_are_hidden(self) -> None:
        built = self.do_import(obj_text("ANIM_begin\nANIM_show 1 2 sim/x\nLIGHT_NAMED beacon 1 2 3\nANIM_end\n", tris=None))
        (light,) = [o for o in built.objects if o.type == "LIGHT"]
        self.assertTrue(light.hide_viewport)

    def test_emitters_and_magnets(self) -> None:
        body = "EMITTER my_smoke 1 2 3 10 20 30\nMAGNET knee xpad 1 2 3 0 0 0\n"
        built = self.do_import(obj_text(body, tris=None))
        by_type = {e.xplane.special_empty_props.special_type: e for e in self.empties(built)}
        emitter = by_type[xplane_constants.EMPTY_USAGE_EMITTER_PARTICLE].xplane.special_empty_props
        self.assertEqual(emitter.emitter_props.name, "my_smoke")
        magnet = by_type[xplane_constants.EMPTY_USAGE_MAGNET].xplane.special_empty_props
        self.assertEqual(magnet.magnet_props.debug_name, "knee")
        self.assertTrue(magnet.magnet_props.magnet_type_is_xpad)

    # ---- how big things are drawn ----------------------------------------------------------------
    def test_empties_are_drawn_at_a_fraction_of_the_part_on_them(self) -> None:
        built = self.do_import(obj_text(DIAL, vertices=SMALL_VT, tris=None))
        (empty,) = self.empties(built)
        self.assertAlmostEqual(0.1 * xplane_display_sizes.FRACTION, empty.empty_display_size, places=5)

    def test_empties_on_big_and_tiny_parts_stay_within_limits(self) -> None:
        (big,) = self.empties(self.do_import(obj_text(DIAL, tris=None)))
        self.assertAlmostEqual(xplane_display_sizes.MAX_SIZE, big.empty_display_size, places=5)
        create_initial_test_setup()
        tiny_vt = SMALL_VT.replace("0.1", "0.001")
        (tiny,) = self.empties(self.do_import(obj_text(DIAL, vertices=tiny_vt, tris=None), "tiny.obj"))
        self.assertAlmostEqual(xplane_display_sizes.MIN_SIZE, tiny.empty_display_size, places=5)

    def test_every_empty_of_a_chain_is_sized_by_the_part_at_its_end(self) -> None:
        body = "ANIM_begin\nANIM_trans 0 1 0 0 1 0\nANIM_rotate_begin 1 0 0 sim/a\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nANIM_begin\nANIM_rotate_begin 0 1 0 sim/b\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nANIM_begin\nANIM_rotate_begin 0 0 1 sim/c\nANIM_rotate_key 0 0\nANIM_rotate_key 1 90\nANIM_rotate_end\nTRIS 0 3\nANIM_end\nANIM_end\nANIM_end\n"
        built = self.do_import(obj_text(body, vertices=SMALL_VT, tris=None))
        self.assertEqual(len(self.empties(built)), 2)  # the third turn is on the part
        for empty in self.empties(built):
            self.assertAlmostEqual(0.1 * xplane_display_sizes.FRACTION, empty.empty_display_size, places=5)

    def test_an_empty_with_nothing_visible_on_it_is_small(self) -> None:
        body = "ANIM_begin\nANIM_show 1 2 sim/x\nLIGHT_NAMED beacon 1 2 3\nLIGHT_NAMED beacon 4 5 6\nANIM_end\n"
        (empty,) = self.empties(self.do_import(obj_text(body, tris=None)))
        self.assertAlmostEqual(xplane_display_sizes.BARE_SIZE, empty.empty_display_size, places=5)

    def test_magnets_and_emitters_keep_a_visible_size(self) -> None:
        built = self.do_import(obj_text("EMITTER my_smoke 1 2 3 10 20 30\nMAGNET knee xpad 1 2 3 0 0 0\n", tris=None))
        for empty in self.empties(built):
            self.assertAlmostEqual(PartsBuilder.EXTRA_EMPTY_SIZE, empty.empty_display_size, places=5)

    def test_the_scale_option_scales_the_sizes_too(self) -> None:
        built = self.do_import(obj_text(DIAL, vertices=SMALL_VT, tris=None), scale=10.0)
        (empty,) = self.empties(built)
        self.assertAlmostEqual(1.0 * xplane_display_sizes.FRACTION, empty.empty_display_size, places=4)

    def test_spot_cones_are_short(self) -> None:
        light = self.light("LIGHT_PARAM airplane_generic_pm 1 2 3 1 0.5 0 18 25cd 0 -1 0 0.5\n")
        self.assertEqual("SPOT", light.data.type)
        self.assertTrue(light.data.use_custom_distance)
        self.assertAlmostEqual(xplane_display_sizes.CONE_LENGTH, light.data.cutoff_distance, places=5)

    def test_a_lit_spill_light_keeps_blenders_distance_so_it_lights_as_it_should(self) -> None:
        light = self.light("LIGHT_PARAM airplane_generic_pm 1 2 3 1 0.5 0 18 25cd 0 -1 0 0.5\n", light_strength=1.0)
        self.assertGreater(light.data.energy, 0.0)
        self.assertFalse(light.data.use_custom_distance)

    def test_a_lit_spill_light_with_a_size_in_meters_is_drawn_that_far(self) -> None:
        light = self.light("LIGHT_SPILL_CUSTOM 1 2 3 0.9 0.8 0.7 1 0.4 0 0 -1 0.5 my/dataref\n", light_strength=1.0)
        self.assertTrue(light.data.use_custom_distance)
        self.assertAlmostEqual(0.4, light.data.cutoff_distance, places=5)

    def test_a_spill_light_with_a_size_in_meters_has_a_cone_of_that_length(self) -> None:
        light = self.light("LIGHT_SPILL_CUSTOM 1 2 3 0.9 0.8 0.7 1 0.4 0 0 -1 0.5 my/dataref\n")
        self.assertTrue(light.data.use_custom_distance)
        self.assertAlmostEqual(0.4, light.data.cutoff_distance, places=5)

    def test_point_lights_are_left_as_they_are(self) -> None:
        light = self.light("LIGHT_SPILL_CUSTOM 0 0 0 1 1 1 1 2 0 0 0 1 none\n")
        self.assertEqual("POINT", light.data.type)
        self.assertFalse(light.data.use_custom_distance)

    # ---- LODs and failures ---------------------------------------------------------------------
    def test_only_the_first_lod_by_default(self) -> None:
        body = "ATTR_LOD 0 500\nTRIS 0 3\nATTR_LOD 500 2000\nTRIS 0 3\n"
        self.assertEqual(len(self.meshes(self.do_import(obj_text(body, tris=None)))), 1)
        create_initial_test_setup()
        self.assertEqual(len(self.meshes(self.do_import(obj_text(body, tris=None), "other.obj", all_lods=True))), 2)

    def test_all_lods_set_up_the_buckets(self) -> None:
        body = "ATTR_LOD 0 500\nTRIS 0 3\nATTR_LOD 500 2000\nTRIS 0 3\n"
        built = self.do_import(obj_text(body, tris=None), all_lods=True)
        layer = built.collection.xplane.layer
        self.assertEqual(layer.lods, "2")
        self.assertEqual([(l.near, l.far) for l in list(layer.lod)[:2]], [(0, 500), (500, 2000)])
        flags = sorted(tuple(o.xplane.lod) for o in self.meshes(built))
        self.assertEqual(flags, [(False, True, False, False), (True, False, False, False)])

    def test_a_bad_file_is_reported_not_raised(self) -> None:
        path = write_file(self.folder.join("bad.obj"), "not an obj")
        self.assertIsNone(import_obj_file(path, ImportOptions(), self.report))
        self.assertEqual(self.report.files_failed, 1)
        self.assertEqual(len(self.report.errors), 1)
        self.assertFalse(bpy.data.collections)

    def test_report_summary(self) -> None:
        self.do_import(obj_text("LIGHT_NAMED beacon 1 2 3\n"))
        summary = self.report.summary()
        self.assertIn("1 file(s)", summary)
        self.assertIn("1 meshes", summary)
        self.assertIn("1 lights", summary)

    def test_importing_twice_keeps_both(self) -> None:
        self.do_import(obj_text(""))
        self.do_import(obj_text(""))
        self.assertEqual(len([c for c in bpy.data.collections if c.name.startswith("thing")]), 2)
        self.assertEqual(len(bpy.data.objects), 2)


runTestCases([TestImportObj])
