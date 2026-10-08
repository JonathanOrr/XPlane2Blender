"""Shared by the importer's round trip tests: a small shape to animate and the dataref values to pose it at"""

from io_xplane2blender.xplane_importer.obj_parser import AnimNode

# A little house shape: a floor quad and a wall quad, so that every transform is visible in the corners
HOUSE_VT = (
    "VT 0 0 0 0 1 0 0 0\nVT 0 0 -1 0 1 0 0 1\nVT 1 0 -1 0 1 0 1 1\nVT 1 0 0 0 1 0 1 0\n"
    "VT 0 0 0 0 0 1 0 0\nVT 1 0 0 0 0 1 1 0\nVT 1 1 0 0 0 1 1 1\nVT 0 1 0 0 0 1 0 1\n"
)
HOUSE_IDX = "IDX10 0 1 2 0 2 3\nIDX10 4 5 6 4 6 7\n"


def all_datarefs(obj):
    keys = {}

    def visit(node):
        for op in node.ops:
            if not op.is_static:
                keys.setdefault(op.dataref, set()).update(k[0] for k in op.keys)
        for line in node.visibility:
            keys.setdefault(line.dataref, set()).update((line.v1, line.v2))
        for child in node.children:
            if isinstance(child, AnimNode):
                visit(child)

    visit(obj.root)
    return keys


def test_values(obj):
    """Several settings of the datarefs: every key, and between keys"""
    datarefs = all_datarefs(obj)
    sets = []
    for choice in range(4):
        values = {}
        for path, keys in datarefs.items():
            ordered = sorted(keys)
            if choice == 0:
                values[path] = 0.0
            elif choice == 1:
                values[path] = ordered[-1]
            elif choice == 2:
                values[path] = ordered[0]
            else:
                values[path] = (ordered[0] + ordered[-1]) / 2 + 0.123 * (
                    ordered[-1] - ordered[0]
                )
        sets.append(values)
    return sets
