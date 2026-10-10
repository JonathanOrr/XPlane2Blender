"""
The pages in docs/ still describe the add-on: the settings reference is what the panels draw, every name the pages
give in bold is one Blender shows, every panel, menu and button is described somewhere, and the pictures they show
exist. See docs/maintaining-the-docs.md.
"""

import glob
import json
import os
import re
import sys

import bpy

from io_xplane2blender.tests import *

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DOCS = os.path.join(REPO, "docs")
TOOLS = os.path.join(DOCS, "tools")
sys.path.insert(0, TOOLS)

import reference  # noqa: E402
from shots import SHOTS, prepare, record  # noqa: E402

BOLD = re.compile(r"\*\*([^*]+?)\*\*")
SHORTCUT = re.compile(r"^(Shift|Ctrl|Alt|Cmd)\+\S+$")


def _pages(guides_only: bool = False):
    """The pages a user reads: the guides, without the generated reference, and the repository's README"""
    pages = [p for p in sorted(glob.glob(os.path.join(DOCS, "*.md"))) if os.path.basename(p) != "reference.md"]
    if not guides_only:
        pages.append(os.path.join(REPO, "README.md"))
    return pages


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _normal(name: str) -> str:
    name = " ".join(name.split()).rstrip(":").strip()
    for end in ("...", "…"):
        if name.endswith(end):
            name = name[: -len(end)].strip()
    return re.sub(r"\d+", "N", name)


def _list_file(name: str):
    """The names of a list in docs/tools: one per line, a # starts a comment (the reason)"""
    found = set()
    for line in _read(os.path.join(TOOLS, name)).splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            found.add(line)
    return found


def _ours(cls) -> bool:
    return getattr(cls, "__module__", "").startswith("io_xplane2blender")


def _registered(base):
    for name in dir(bpy.types):
        cls = getattr(bpy.types, name)
        if isinstance(cls, type) and issubclass(cls, base) and _ours(cls):
            yield cls


def _texts(node, found) -> None:
    if isinstance(node, dict):
        if isinstance(node.get("text"), str) and node["text"]:
            found.add(node["text"])
        for value in node.values():
            _texts(value, found)
    elif isinstance(node, list):
        for value in node:
            _texts(value, found)


class TestDocsText(XPlaneTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.reference = reference.markdown()

    def known_names(self):
        names = set()
        # What the reference lists: every name, every choice and every heading
        for line in self.reference.splitlines():
            if line.startswith("### "):
                names.add(line[4:])
            elif line.startswith("| ") and not line.startswith("| Name ") and not line.startswith("|---"):
                cells = [cell.strip() for cell in line.strip("|").split(" | ")]
                names.update(cells[:2])
                names.update(part.strip() for part in cells[0].split(" > "))
                for choices in re.findall(r"Choices: (.*?)\.(?: |$)", line):
                    names.update(choice.strip() for choice in choices.split(", "))
        # What the screenshots' panels show now, in the demo scene (not the saved records, which may be out of date)
        for shot in SHOTS:
            prepare(shot)
            _texts(record(shot), names)
        # Labels of panels, menus and tools, and the operators with their options
        for base in (bpy.types.Panel, bpy.types.Menu):
            names.update(cls.bl_label for cls in _registered(base))
        for cls in _registered(bpy.types.Operator):
            names.add(cls.bl_label)
            module, _, name = cls.bl_idname.partition(".")
            rna = getattr(getattr(bpy.ops, module), name).get_rna_type()
            for prop in rna.properties:
                names.add(prop.name)
                if prop.type == "ENUM":
                    names.update(item.name for item in prop.enum_items)
        names.update(cls.bl_label for cls in bpy.types.WorkSpaceTool.__subclasses__() if _ours(cls))
        names.update(reference.MENU_TITLES.values())
        names.update(_list_file("blender_names.txt"))
        return {_normal(name) for name in names if name}

    def reference_rows(self, panels_only: bool = False):
        """(name, kind) of the reference's rows: its tables have the kind in the second or third column. The panels'
        rows come before the menus'"""
        kinds = ("setting", "button", "icon button", "menu")
        for line in self.reference.splitlines():
            if panels_only and line.startswith("## Menus"):
                break
            if not line.startswith("| ") or line.startswith("|---"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split(" | ")]
            if len(cells) >= 2 and cells[1] in kinds:
                yield cells[0], cells[1]
            elif len(cells) >= 3 and cells[2] in kinds:
                yield cells[1], cells[2]

    def test_reference_is_current(self) -> None:
        # Blender's own tooltips (a name's, for example) change between its versions
        with open(os.path.join(DOCS, "images", "blender_version.txt")) as f:
            version = f.read().strip()
        if version != "%d.%d" % bpy.app.version[:2]:
            self.skipTest(f"the reference is written with Blender {version}")
        with open(os.path.join(DOCS, "reference.md"), encoding="utf-8") as f:
            saved = f.read()
        if saved != self.reference:
            old, new = saved.splitlines(), self.reference.splitlines()
            line = next((i for i, (a, b) in enumerate(zip(old, new)) if a != b), min(len(old), len(new)))
            self.fail(
                f"docs/reference.md is out of date at line {line + 1}:\n  {old[line] if line < len(old) else ''}\n"
                f"  {new[line] if line < len(new) else ''}\n"
                "Write it again: blender -b --factory-startup --python docs/tools/reference.py"
            )

    def test_bold_names_are_names_blender_shows(self) -> None:
        known = self.known_names()
        unknown = []
        for page in _pages():
            # A quoted note (the fork notice) may use bold for emphasis
            text = "\n".join(line for line in _read(page).splitlines() if not line.lstrip().startswith(">"))
            for bold in BOLD.findall(text):
                for part in bold.split(" > "):
                    name = _normal(part)
                    if SHORTCUT.match(part.strip()) or name in known:
                        continue
                    if any(other.startswith(name + " ") for other in known):
                        continue  # The start of a name that holds a file name, such as Bake For cockpit.obj
                    unknown.append(f"{os.path.relpath(page, REPO)}: **{bold}**")
        self.assertFalse(
            unknown,
            "These bold names are not shown anywhere in Blender (renamed or removed?). Bold is only for names Blender"
            " shows; Blender's own are in docs/tools/blender_names.txt:\n  " + "\n  ".join(unknown),
        )

    def test_every_panel_menu_and_button_is_in_a_guide(self) -> None:
        written = set()
        for page in _pages(guides_only=True):
            written.update(_normal(part) for bold in BOLD.findall(_read(page)) for part in bold.split(" > "))
        exempt = {_normal(name) for name in _list_file("not_in_guides.txt")}
        required = set()
        for cls in _registered(bpy.types.Panel):
            if cls.bl_label:
                required.add(cls.bl_label)
        required.update(cls.bl_label for cls in _registered(bpy.types.Menu))
        # Buttons with a name on them; key values and file names change with the scene
        required.update(
            name
            for name, kind in self.reference_rows(panels_only=True)
            if kind in ("button", "menu") and not re.search(r"^[\d.-]+$|\.obj\b|^In ", name)
        )
        missing = sorted(
            name
            for name in required
            if _normal(name) not in written
            and _normal(name) not in exempt
            and not any(w.startswith(_normal(name) + " ") or _normal(name).startswith(w + " ") for w in written)
        )
        self.assertFalse(
            missing,
            "Not described in any guide in docs/ (in bold). Describe them where they belong, or list them in"
            " docs/tools/not_in_guides.txt with the reason:\n  " + "\n  ".join(missing),
        )

    def test_pictures_shown_and_there(self) -> None:
        shown = set()
        for page in _pages():
            for name in re.findall(r"images/([\w-]+\.png)", _read(page)):
                shown.add(name)
                self.assertTrue(os.path.exists(os.path.join(DOCS, "images", name)), f"{page} shows images/{name}")
        for path in glob.glob(os.path.join(DOCS, "images", "*.png")):
            self.assertIn(os.path.basename(path), shown, f"docs/images/{os.path.basename(path)} is in no page")


runTestCases([TestDocsText])
