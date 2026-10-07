import numpy as np

from io_xplane2blender.tests import *
from io_xplane2blender.tests.importer_helpers import obj_text
from io_xplane2blender.xplane_importer import obj_parser
from io_xplane2blender.xplane_importer.obj_parser import (
    AnimNode,
    Light,
    ObjParseError,
    TrisRun,
    parse_obj,
)


def state(run: TrisRun) -> dict:
    return dict(run.state)


class TestObjParser(XPlaneTestCase):
    def test_header_variants(self) -> None:
        for header in ("A\n800\nOBJ\n", "I\n800\nOBJ\n", "A\r\n800\r\nOBJ\r\n"):
            with self.subTest(header=header.replace("\r", "\\r")):
                text = header + "VT 0 0 0 0 1 0 0 0\nIDX 0\nTRIS 0 1\n"
                obj = parse_obj(text)
                self.assertEqual(obj.version, 800)
                self.assertEqual(len(obj.vertices), 1)

    def test_not_an_obj_is_rejected(self) -> None:
        with self.assertRaises(ObjParseError):
            parse_obj("# www.blender3d.org\nv 0 0 0\n")
        with self.assertRaises(ObjParseError):
            parse_obj("A\n700\nOBJ\n")

    def test_tables(self) -> None:
        obj = parse_obj(obj_text("", vertices="VT 1 2 3 0 1 0 0.5 0.25 # 0\nVT 4 5 6 0 1 0 1 1\n", indices="IDX 0\nIDX10 1 0 1\n"))
        self.assertEqual(obj.vertices.shape, (2, 8))
        self.assertEqual(list(obj.vertices[0]), [1, 2, 3, 0, 1, 0, 0.5, 0.25])
        self.assertEqual(list(obj.indices), [0, 1, 0, 1])

    def test_textures_and_globals(self) -> None:
        obj = parse_obj(
            obj_text(
                "",
                header="TEXTURE a b.png\nTEXTURE_LIT c.png\nTEXTURE_NORMAL 0.5 n.png\nNORMAL_METALNESS\nGLOBAL_specular 0.7\nBLEND_GLASS\n"
                "TEXTURE_MAP normal x.png\nTEXTURE_MAP material_gloss y.png\n",
            )
        )
        self.assertEqual(obj.texture, "a b.png")
        self.assertEqual(obj.texture_lit, "c.png")
        self.assertEqual(obj.texture_normal, "n.png")
        self.assertTrue(obj.has_normal_metalness)
        self.assertEqual(obj.globals["GLOBAL_specular"], [["0.7"]])
        self.assertIn("BLEND_GLASS", obj.globals)
        self.assertEqual(obj.texture_maps, {"normal": "x.png", "material_gloss": "y.png"})

    def test_attribute_state_machine(self) -> None:
        body = (
            "ATTR_shiny_rat 0.5\nTRIS 0 3\n"
            "ATTR_no_blend 0.3\nATTR_draw_disable\nTRIS 0 3\n"
            "ATTR_draw_enable\nATTR_blend\nTRIS 0 3\n"
            "ATTR_reset\nTRIS 0 3\n"
        )
        runs = list(parse_obj(obj_text(body, tris=None)).iter_tris())
        self.assertEqual(len(runs), 4)
        self.assertEqual(state(runs[0]), {"shiny": ("0.5",)})
        self.assertEqual(state(runs[1]), {"shiny": ("0.5",), "blend": ("no_blend", "0.3"), "draw": ("disable",)})
        self.assertEqual(state(runs[2]), {"shiny": ("0.5",), "blend": ("blend",)})
        self.assertEqual(state(runs[3]), {})

    def test_equal_states_compare_equal(self) -> None:
        body = "ATTR_cull\nTRIS 0 3\nATTR_no_cull\nATTR_cull\nTRIS 0 3\n"
        runs = list(parse_obj(obj_text(body, tris=None)).iter_tris())
        self.assertEqual(runs[0].state, runs[1].state)

    def test_light_level_and_manipulators(self) -> None:
        body = (
            "ATTR_light_level 0 1 sim/some/dataref\nATTR_manip_command button sim/cmd/x A tooltip with spaces\nTRIS 0 3\n"
            "ATTR_manip_wheel 0.5\nATTR_axis_detent_range 0 1 0.1\nATTR_manip_none\nATTR_light_level_reset\nTRIS 0 3\n"
        )
        runs = list(parse_obj(obj_text(body, tris=None)).iter_tris())
        first = state(runs[0])
        self.assertEqual(first["light_level"], ("0", "1", "sim/some/dataref"))
        self.assertEqual(first["manip"], ("command", "button", "sim/cmd/x", "A", "tooltip", "with", "spaces"))
        self.assertEqual(state(runs[1]), {})

    def test_manip_extras_belong_to_their_manipulator(self) -> None:
        body = (
            "ATTR_manip_drag_axis hand 0 1 0 0 1 sim/d tip\nATTR_manip_wheel 0.25\nATTR_axis_detent_range 0 0.5 0.1\nTRIS 0 3\n"
            "ATTR_manip_command button sim/c tip\nTRIS 0 3\n"
        )
        runs = list(parse_obj(obj_text(body, tris=None)).iter_tris())
        first, second = state(runs[0]), state(runs[1])
        self.assertEqual(first["manip_extras"], (("ATTR_manip_wheel", ("0.25",)),))
        self.assertEqual(first["manip_detents"], (("0", "0.5", "0.1"),))
        self.assertNotIn("manip_extras", second)
        self.assertNotIn("manip_detents", second)

    def test_anim_blocks_nest(self) -> None:
        body = (
            "ANIM_begin\nANIM_trans 1 2 3 1 2 3\nANIM_rotate 0 1 0 90 90\n"
            "ANIM_rotate_begin 1 0 0 sim/rot\nANIM_rotate_key 0 0\nANIM_rotate_key 1 45\nANIM_rotate_end\n"
            "ANIM_begin\nANIM_trans_begin sim/t\nANIM_trans_key 0 0 0 0\nANIM_trans_key 1 0 1 0\nANIM_trans_end\nANIM_keyframe_loop 360\n"
            "TRIS 0 3\nANIM_end\nANIM_end\n"
        )
        obj = parse_obj(obj_text(body, tris=None))
        outer = obj.root.children[0]
        self.assertIsInstance(outer, AnimNode)
        self.assertEqual([op.kind for op in outer.ops], ["trans", "rotate", "rotate"])
        self.assertTrue(outer.ops[0].is_static and outer.ops[1].is_static)
        self.assertFalse(outer.ops[2].is_static)
        self.assertEqual(outer.ops[2].keys, [(0.0, (0.0,)), (1.0, (45.0,))])
        inner = outer.children[0]
        self.assertEqual(inner.ops[0].kind, "trans")
        self.assertEqual(inner.ops[0].keys[1], (1.0, (0.0, 1.0, 0.0)))
        self.assertEqual(inner.ops[0].loop, 360.0)
        self.assertIsInstance(inner.children[0], TrisRun)

    def test_old_style_keyed_ops(self) -> None:
        body = "ANIM_begin\nANIM_trans 0 0 0 0 1 0 0 10 sim/x\nANIM_rotate 0 0 1 -10 20 0 1 sim/y\nTRIS 0 3\nANIM_end\n"
        node = parse_obj(obj_text(body, tris=None)).root.children[0]
        self.assertEqual(node.ops[0].keys, [(0.0, (0.0, 0.0, 0.0)), (10.0, (0.0, 1.0, 0.0))])
        self.assertEqual(node.ops[1].keys, [(0.0, (-10.0,)), (1.0, (20.0,))])
        self.assertEqual(node.ops[1].dataref, "sim/y")

    def test_show_and_hide(self) -> None:
        body = "ANIM_begin\nANIM_show 1 2 sim/a\nANIM_hide 0.5 1.5 sim/b[3]\nTRIS 0 3\nANIM_end\n"
        node = parse_obj(obj_text(body, tris=None)).root.children[0]
        self.assertEqual([(v.kind, v.v1, v.v2, v.dataref) for v in node.visibility], [("show", 1.0, 2.0, "sim/a"), ("hide", 0.5, 1.5, "sim/b[3]")])

    def test_lights(self) -> None:
        body = (
            "LIGHT_NAMED beacon 1 2 3\nLIGHT_PARAM airplane_nav_left 1 2 3 0 0\n"
            "LIGHT_CUSTOM 1 2 3 1 1 1 1 5 0 0 1 0 0 1 1 sim/x\n"
        )
        lights = [c for c in parse_obj(obj_text(body, tris=None)).root.children if isinstance(c, Light)]
        self.assertEqual([(l.kind, l.name, l.position) for l in lights], [("named", "beacon", (1.0, 2.0, 3.0)), ("param", "airplane_nav_left", (1.0, 2.0, 3.0)), ("custom", "", (1.0, 2.0, 3.0))])
        self.assertEqual(lights[1].args, ["0", "0"])

    def test_lods_reset_the_state(self) -> None:
        body = "ATTR_no_cull\nATTR_LOD 0 1000\nTRIS 0 3\nATTR_LOD 1000 3000\nTRIS 0 3\n"
        obj = parse_obj(obj_text(body, tris=None))
        runs = list(obj.iter_tris())
        self.assertEqual(obj.lods, [(0.0, 1000.0), (1000.0, 3000.0)])
        self.assertEqual([r.lod for r in runs], [(0.0, 1000.0), (1000.0, 3000.0)])
        self.assertEqual(state(runs[0]), {})

    def test_unknown_directives_are_kept_not_dropped(self) -> None:
        obj = parse_obj(obj_text("FUTURE_THING 1 2\nFUTURE_THING 3\nTRIS 0 3\n", tris=None))
        self.assertEqual(obj.unknown, {"FUTURE_THING": 2})

    def test_comments_and_blank_lines(self) -> None:
        body = "\n# a comment\n   \nANIM_begin # trailing\nTRIS 0 3 # more\nANIM_end\n"
        node = parse_obj(obj_text(body, tris=None)).root.children[0]
        self.assertEqual(node.comment, "a comment")
        self.assertEqual(node.children[0].count, 3)

    def test_bad_lines_become_warnings(self) -> None:
        obj = parse_obj(obj_text("ANIM_begin\nANIM_rotate_begin 1 0 0 sim/x\nANIM_rotate_key 0 oops\nANIM_rotate_end\nANIM_end\n", tris=None))
        self.assertEqual(len(obj.warnings), 1)
        self.assertIn("ANIM_rotate_key", obj.warnings[0])

    def test_numbers_with_stray_text_read_like_x_plane(self) -> None:
        # Laminar's Cessna 172 (vor1_gs_ag.obj) has this, X-Plane reads -2.5
        body = "ANIM_begin\nANIM_rotate_begin 0 0 1 sim/x\nANIM_rotate_key -2.5.000000 -18\nANIM_rotate_key 1e1x 5\nANIM_rotate_end\nANIM_end\n"
        obj = parse_obj(obj_text(body, tris=None))
        self.assertEqual(obj.root.children[0].ops[0].keys, [(-2.5, (-18.0,)), (10.0, (5.0,))])
        # It is still reported, with the line, so a typo in a file is never silent
        self.assertEqual(len(obj.warnings), 2)
        self.assertIn("-2.5.000000", obj.warnings[0])
        self.assertIn("as -2.5", obj.warnings[0])
        self.assertIn("line", obj.warnings[1])

    def test_bad_vertex_table_is_repaired(self) -> None:
        obj = parse_obj(obj_text("", vertices="VT 1 2 3 0 1 0 0 0\nVT 1 2\nVT 4 5 6 0 1 0 0 0\n", indices="IDX10 0 1 2\n"))
        self.assertEqual(obj.vertices.shape, (3, 8))
        self.assertTrue(obj.warnings)

    def test_unclosed_anim_block_warns(self) -> None:
        obj = parse_obj(obj_text("ANIM_begin\nTRIS 0 3\n", tris=None))
        self.assertTrue(any("never closed" in w for w in obj.warnings))

    def test_point_counts_and_texture_paths_with_spaces(self) -> None:
        obj = parse_obj(obj_text("", header="TEXTURE my folder/a b.png\n"))
        self.assertEqual(obj.texture, "my folder/a b.png")
        self.assertEqual(obj.point_counts, (3, 0, 0, 3))


runTestCases([TestObjParser])
