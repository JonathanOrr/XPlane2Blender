# Maintaining The Docs

These pages are tested with the add-on, so a change to the add-on that makes them wrong fails the test suite until
they are updated. This page is for people who change the add-on.

## What The Tests Check

`tests/docs/` runs with the rest of the suite (`python3 tests.py`) and in CI:

| Test | Fails when | What to do |
|---|---|---|
| Screenshots | A panel or menu draws something else than its screenshot shows: a renamed button, a new setting, a changed default | Update the pages that describe it, then take the screenshot again (below) |
| Reference | `docs/reference.md` differs from what the add-on's panels draw | Write it again (below) |
| Names | A page names something in bold that Blender does not show, after a rename or a removal | Use the new name, or take the sentence out |
| Coverage | A panel, menu or button is not named in any guide | Describe it in the guide it belongs to, or, for a button nobody needs to know about, list it in `docs/tools/not_in_guides.txt` with the reason |
| Pictures | A page shows a picture that is not there, or a picture is in no page | Take it, or remove it |

The screenshot test only runs in the Blender version the screenshots were taken with (in
`docs/images/blender_version.txt`); the others run in every version.

## Writing

- Bold is only for names you see in Blender: panels, buttons, settings, menus, tabs, written exactly as Blender
  shows them. The names test reads every bold text, and a path such as **Scene tab > X-Plane Export** part by part.
  Blender's own names (**Properties editor**, **Overlays**, **Edit > Preferences**) are listed in
  `docs/tools/blender_names.txt`. Use `code` for datarefs, commands, file names and OBJ lines.
- A name that holds a file name or a number, such as **Export 2 Files** or **Bake For**, may be written as it shows in
  the demo scene, or as its start. A quoted note (a line starting with `>`) may use bold for emphasis.
- Say what something does for the aircraft, not how the add-on does it.

## Taking The Screenshots

The pictures are taken of a demo cockpit built from nothing by `docs/tools/scenes.py`, in Blender windows that open
and close by themselves (a desktop is needed; each takes a few seconds):

```
python3 docs/tools/make_screenshots.py --blender /path/to/blender-5.2/blender               # all of them
python3 docs/tools/make_screenshots.py --blender /path/to/blender-5.2/blender object_knob   # some of them
```

Each picture is saved with a record of what its panels drew (`docs/images/<name>.ui.json`), which the screenshot test
compares against. Look at the pictures you took before committing them.

To add a screenshot, add a `Shot` to `docs/tools/shots.py` (what is selected, which tab and panels, which sub-panels are
open or left out; windows are at most about 1100 pixels tall, so a long panel is better split into two pictures), add
what it needs to the demo scene in `docs/tools/scenes.py`, take it, and show it in a page.

## Writing The Reference Again

```
blender -b --factory-startup --python docs/tools/reference.py
```

It draws every panel in each of its variants (every kind of control, light, attachment point, screen, table) and lists
what they show with their tooltips. A new variant of a panel goes into `_sections()` in `docs/tools/reference.py`.
The tooltips come from the add-on: fix a wrong one there, not in the page.
