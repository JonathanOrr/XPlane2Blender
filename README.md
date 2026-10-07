[![Tests](https://github.com/JonathanOrr/XPlane2Blender/actions/workflows/tests.yml/badge.svg?branch=develop)](https://github.com/JonathanOrr/XPlane2Blender/actions/workflows/tests.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

> **X-Plane 12 Aircraft Tools is an unofficial fork of [XPlane2Blender](https://github.com/X-Plane/XPlane2Blender)**,
> not affiliated with or supported by Laminar Research. Please report problems with it
> [here](https://github.com/JonathanOrr/XPlane2Blender/issues), not to Laminar Research.

# X-Plane 12 Aircraft Tools
A Blender add-on (Blender 3.6 and up, 5.2 LTS recommended) for making **X-Plane 12 aircraft and cockpits**: import an
aircraft or an OBJ, change it or add to it, and export X-Plane 12 OBJs.

How it differs from XPlane2Blender:
- **X-Plane 12 only.** There is no X-Plane version setting and no scenery. Files made with XPlane2Blender open as they
  are and are converted once when opened: an older X-Plane version setting becomes X-Plane 12 and scenery files become
  aircraft files. Imported OBJs and aircraft from X-Plane 10, 11 and 12 come in set up for X-Plane 12
- **Plain-words panels that follow the selection.** An **X-Plane** panel in the Properties editor's Object, Material,
  Collection and Scene tabs, each showing only what applies to what is selected
- **Work in progress always exports.** Settings that are not filled in yet are left out, never an error
- **An importer** for whole aircraft (.acf) and OBJ files

## Installation
1. Download the add-on .zip from the [releases](https://github.com/JonathanOrr/XPlane2Blender/releases), named like
   `io_xplane2blender_5_0_0-alpha_1-123_20261008120000.zip`. Do not unzip it
2. In Blender, Edit > Preferences > Add-ons: in Blender 4.2 and later use the drop-down at the top right and
   **Install from Disk...**, in older versions **Install...**. Pick the .zip
3. Tick **X-Plane 12 Aircraft Tools**. It replaces XPlane2Blender (same add-on folder), so do not enable both
4. Restart Blender

Always keep backups of your .blend files: a file opened and saved with this add-on has been converted to X-Plane 12.

## The X-Plane Panels
Everything is in the Properties editor, in the tab it belongs to. Blender lists add-on panels after its own, so the
**X-Plane** panel is near the bottom of a tab; drag it to the top by its ⠿ grip once and Blender keeps it there.

**Object tab > X-Plane** shows the active object: what it is in plain words (for example
`Knob, two commands · Moves · Glows`), which OBJ file it exports in, or that it is not in any file and so is not
exported (with **New File** and **Move To File** right there), and what is not filled in yet. Below it, a card for
each thing the object can do:

| Card | For |
|---|---|
| **Clickable** | Make it clickable in the cockpit. **Make Clickable As...** lists the kinds of control by what they do (runs commands, sets a dataref, dragged), and the card then shows only the settings that kind uses, with the help in one line. The search button next to a command or dataref searches X-Plane's own lists and the custom names this file already uses |
| **Light** | For lights: a library light from lights.txt (with a search tagged spill / glow), a spill that lights its surroundings, a glow sprite, or not exported. **Preview As In X-Plane** makes the viewport show it the way X-Plane does |
| **Attachment Point** | For empties: a wheel, a VR tablet mount or a particle emitter |
| **Moves** | The **Button**, **Switch** and **Knob / Lever** presets key a whole control on every selected object in one step. An animated object lists its datarefs and its keys as buttons (click one to go to it); to key by hand, pose the object, type the dataref value and click **Key Pose** |
| **Shows / Hides** | Show or hide it while a dataref is in a range |
| **Glow** | The night (LIT) texture's brightness follows a dataref, like a backlight on a dimmer |
| **Advanced** | HUD glass, rain, draw order, levels of detail, custom attributes, and **Every Setting (Classic)** with the complete earlier layout |

With several objects selected, the copy button in a card's header copies that card's settings from the active object
to the others.

**Material tab > X-Plane** is the material's surface, shared by every object using it: visible or invisible
(invisible click zones), transparency, shadows, camera collision, a screen (the 2D panel or an avionics device with
its power buses) and the material's glow. **More** and **Every Setting (Classic)** are below it.

**Collection tab > X-Plane**: tick it to export the collection as an OBJ file, with its name and kind (aircraft part
or cockpit). **File Settings And Export** opens the file in the Scene tab.

**Scene tab > X-Plane Export** lists the OBJ files of the scene: tick a collection to export it, click **Cockpit** /
**Part** to switch its kind, the arrow selects its objects. **Export N Files** writes them next to the .blend file.
**New File From Selection** puts the selected objects (with their children) in a new file, taking them out of the
files they were in, and fills in its textures from their materials. Under the list are the chosen file's settings:
textures (with **From Materials**), look, cockpit panel, levels of detail, X-Plane 12 texture maps, rain and wipers,
detail textures and more.

**Scene tab > X-Plane Unfinished Work** lists what is not filled in yet in the export files, with a button to select
each object.

**Scene tab > X-Plane Tools** has **Find and Replace**, **Table**, the click zone overlay and the light preview for
every light.

Also: **Shift+A > X-Plane** adds an invisible click zone, a light or an attachment point at the 3D cursor; the
viewport's right-click menu has **X-Plane > Make Clickable As**, the animation presets and **Move To File**; and the
viewport's **Overlays** popover can outline everything clickable (orange runs commands, blue sets datarefs, green is
dragged) and label it with what a click does.

### A coffee cup in the cup holder
1. Model or append the cup, give it a material with an image texture
2. Select it, then Scene tab > X-Plane Export > **New File From Selection**, name it `coffee_cup`
3. Save the .blend in your aircraft's `objects` folder (OBJs are written next to the .blend) and click **Export 1 File**
4. Add `coffee_cup.obj` to the aircraft in Plane Maker (Standard > Objects)

## Exporting Work In Progress
You can export at any stage: settings you have started but not filled in yet are left out of the OBJ instead of stopping the export, and the status bar counts them, for example `Exported 10 file(s); left out as unfinished: 61 light levels without a dataref`. The full list is in the `XPlane2Blender.log` text file. This covers light levels without a dataref (an empty one would write an invalid line), meshes without a material (they export with X-Plane's default material state) and library lights with no light chosen yet. A file with a real error is not written, but the other files of the export still are, and the status bar says which ones were skipped.

## Find And Replace, Duplicate And Replace
For the many controls that differ only by side or number. **Scene tab > X-Plane Tools > Find and Replace**: add pairs such as `cockpit/mcdu/` → `cockpit/mcdu_2/` and `Captain` → `First Officer`, choose which settings to touch (commands, datarefs, light levels, tooltips, custom attributes) and which objects (selected, selected and their children, or the whole scene), and the panel previews every change before you apply it.
- **Find and Replace** changes the objects in place.
- **Duplicate and Replace** copies the selection, renames the settings on the copies only and lets you move them, like Shift+D. Copy the captain's MCDU once and the first officer's is done.
- Pairs are applied in order, **Match Case** is on by default (X-Plane names are case sensitive) and **Regex** allows regular expressions with `\1` groups.
- A material or light that objects outside the selection also use is left alone, so changing one side never changes the other. The panel says how many were skipped.
- Both are normal Blender operations: Ctrl+Z undoes them and the Adjust Last Operation panel works.

## Tables And CSV
**Scene tab > X-Plane Tools > Table** lists every object with a manipulator, a light level or animation datarefs in one place. Click a row to select that object in the viewport, type in the search box to filter by name, command or dataref, and widen the Properties editor to edit the type, command and tooltip in place (a narrow one shows the end of each command, where `key/A` and `key/B` differ). **Export CSV** writes every setting of the listed objects to a spreadsheet file, and **Import CSV** reads it back by object name: values that did not change are left alone, and objects that are not found or values that cannot be used are reported instead of stopping the import. Keyframes stay in Blender; the animation table holds the dataref paths and show/hide values.

## Animation Presets
In the **Moves** card (and the viewport's right-click menu), on every selected object:
- **Button** moves the button in while its command is held, with a `CMND=` dataref. Leave the command empty and each button uses its own manipulator command, so a hundred buttons get their animation in one click. Buttons without a manipulator get one (tick off **Make Clickable** to skip that).
- **Switch** gives each of a number of positions a dataref value and an angle or a distance, for toggles, rotary selectors and pull switches. The dialog shows the result, for example `0 → 20°  1 → 0°  2 → -20°`.
- **Knob / Lever** follows a dataref over a range, turning or sliding. **Loop Every** makes an endless knob.

Movement is along or around the object's own axis, from where it stands. Keys are linear, as X-Plane interpolates them, and turns over 90° get extra keys in between so whole turns are kept. `{name}` in a command or dataref becomes the object's name. Objects that are already animated are left alone unless **Replace** is ticked, and Replace starts again from where the object stood before the preset first animated it. On the A321XLR cockpit the Button preset reproduces 40 of 40 hand-made button animations key for key.

## Lights
- The search button next to a light's **Name** lists every light in lights.txt, tagged **spill** (lights its surroundings), **glow** (a visible halo that lights nothing) or both. Under the name, the card says what the chosen light is, or that the name is not in lights.txt.
- For **Library Light, Typed Parameters** the card lists the parameters in order and says when the typed values are too few or too many.
- **Preview As In X-Plane** makes lights look in the viewport the way X-Plane draws them: spill lights light their surroundings, custom spills only out to their reach in meters, and glow-only and custom lights light nothing. It only changes Blender settings the exporter never reads (power, except for glow sprites whose power is the exported alpha, cutoff distance and ray visibility), so the exported OBJ stays the same. Ctrl+Z undoes it.
- Old X-Plane 9 lights (`LIGHTS`) still export as before; the Light card offers the X-Plane 12 kinds to replace them.

## Importing X-Plane Aircraft And Objects
Open **File > Import > X-Plane Aircraft (.acf)**, pick an aircraft's `.acf` file, and the whole aircraft is brought in: every object it lists, in the right place, with its textures, normal maps, materials, animations, manipulators and lights. It works with the text based `.acf` files of X-Plane 10, 11 and 12. **File > Import > X-Plane Object (.obj)** imports single OBJ8 files (several at once is fine), and you can also drag an `.acf` or `.obj` onto the 3D viewport in Blender 4.1 and later.

The options are in the side panel of the file browser:

| Option | What it does |
|---|---|
| Livery | Uses the textures of one of the aircraft's liveries instead of the default ones |
| Textures and Materials | Loads the images and builds shader nodes (albedo, normal map, gloss, metalness, alpha cutoff, the `_LIT` texture) |
| Animations | Creates the dataref animations (Empties with keyframes) and show/hide settings |
| Manipulators | Sets up the clickable manipulators, with their commands, datarefs and tooltips |
| Lights | Creates lights with their XPlane2Blender settings. See "How lights come in" below |
| All LODs | Imports every level of detail instead of only the first |
| Hide What X-Plane Hides | Hides the objects that X-Plane would not draw with the datarefs at their default values. Unhide them before exporting again, hidden objects are not exported |
| Make Export Roots | Ticks each OBJ's collection as an export file. Off by default, because exporting a whole aircraft would write every file. The texture and export settings are always filled in and the files are listed unticked in the Scene tab's X-Plane Export panel, so one tick exports one again |
| Night Light Strength | How much the `_LIT` texture glows, 0 shows the daytime look |
| Light Strength | Switches the spill lights on, such as the cockpit annunciator and panel lights. 0 keeps them from lighting the scene (they are off in the parked pose), 1 is the brightness the light's parameters ask for |
| Damage / Part Attached / Not Drawn Objects | Also brings in objects that are normally left out (they only show when a part breaks, move with a wing or gear part, or are drawn nowhere) |

What you get:
- Each OBJ becomes a collection, grouped under the aircraft's collection. Animated parts sit under Empties named after their datarefs, with the scene opening in the parked pose (landing gear down, flaps in, and so on)
- Animations are keyframed so that **frame 1 is the parked pose**, with linear interpolation like X-Plane
- Meshes with different manipulators, light levels or materials are separate objects, so everything can be edited and exported again
- Anything the add-on has no setting for is kept as a custom attribute, or reported as a warning, never silently dropped

How lights come in:
- `lights.txt` gives a light a **billboard** (the visible halo, lights nothing) and/or a **spill** (really lights its surroundings). Spills become Blender point or spot lights, with the cone and direction from the light's parameters (`WIDTH` is the cosine of half the cone angle, `DX DY DZ` the direction) and the power from its candela or radius. Billboards and `LIGHT_CUSTOM` halos are kept for export but do not light the scene in Cycles or EEVEE
- The numbers are for a plausible picture, not a measurement. The exporter writes a light's parameters as stored and never reads the power of a named, parameterized or spill light, so you can change the Blender power freely. The power the light has when on is stored on the light as `xplane_watts_when_on`
- `LIGHT_CUSTOM` is the exception: the exporter writes the Blender power as the light's alpha, and colors outside 0 to 1 (some halos use -1 as a placeholder) use the "RGB Picker Override"
- Re-exporting writes the same parameters, and the same position and direction in the aircraft. XPlane2Blender always writes an alpha of 1 for `LIGHT_SPILL_CUSTOM` and normalizes its direction, the importer warns when an alpha was different

Limits worth knowing:
- Wings and fuselages that Plane Maker builds from its own parts (not from OBJ files) are not imported, only the OBJ objects are
- Objects attached to a wing, gear or body part are skipped by default, their placement depends on that part
- Textures in the BC6/BC7 DDS formats can't be read by Blender, those materials have no image
- Re-exporting complex drag rotate manipulators needs the parent and child animation layout XPlane2Blender asks for
- Imported textures are referenced by their full path, keep the aircraft where it is or relink them in Blender

## Relationship To XPlane2Blender
This fork started from XPlane2Blender 4.5 and diverged at the tag `upstream-base`. The exporter core (`xplane_types/`,
`xplane_export.py`) is kept close to upstream, including its code for older X-Plane versions that the add-on no longer
offers, so fixes can move both ways:
- A fix that also applies to XPlane2Blender: branch from `upstream-base`, fix it there with its test, then merge that
  branch into `develop`. The same branch can be offered upstream as it is
- A fix from XPlane2Blender: cherry-pick it onto `develop`
- The upstream test suite runs on every push with `XPLANE2BLENDER_KEEP_OLD_SETTINGS=1`, so its test files keep the
  X-Plane version they were saved with

## Documentation Sources
- [XPlane2Blender Manual](https://xp2b-docs.gitbook.io/xplane2blender-docs)
- [The PZL-M-18, an open source aircraft](https://github.com/todirbg/PZL-M-18)
- [The BD-5J Microjet, an open source jet](https://forums.x-plane.org/index.php?/files/file/27269-bd-5j-microjet)
- [Dan Klaue's "Using Blender With PlaneMaker" Playlist](https://www.youtube.com/playlist?list=PLDB0F4B925CF9169C). While older it still explains many of the principles of XPlane2Blender
- [X-Plane Scenery File Formats](http://developer.x-plane.com/docs/specs/)
- [X-Plane.org's 3d Modeling board](https://forums.x-plane.org/index.php?/forums/forum/45-3d-modeling/)
- [X-Plane Scenery Developer Blog/Knowledge Base](http://developer.x-plane.com/)
- [X-Plane Modeling Tutorials](http://developer.x-plane.com/docs/modeling/)

## Test Suite
**The average user does not need the test suite.** Before releasing a build to the public we test the code many many many times! This is only useful for developers and power users who make changes to the source code. The tests folder must also be in the same folder as the addon folder (see manual installation).

If you have Python 3 installed (it only launches Blender; the tests themselves run on Blender's bundled Python) and the **full source code** downloaded, you can run the test suite. It will attempt to export sample .blend files that utilize various features of the exporter and print the results (see the contents of the ``test`` folder). All passing means XPlane2Blender is safe to use. In the XPlane2Blender folder, open up a command line and run

``python tests.py --print-fails``

This runs the test files in parallel (``-j N`` sets how many at once, default is your CPU count) and stops at the first failing file, or use ``--continue`` to run everything. Only detailed logs will be printed for failed tests, and the exit code is non-zero if anything failed. See ``--help`` to show all flags and what they do.

If Blender isn't in your path, point the test runner at it with ``--blender /path/to/blender``.

## Code Style
New and changed code is formatted with [black](https://github.com/psf/black) and [isort](https://pycqa.github.io/isort/), applied only to the lines you touch so that old code isn't reformatted wholesale. To set it up:

```
pip install -r requirements.txt
pre-commit install
```

[ruff](https://docs.astral.sh/ruff/) also runs to catch real bugs like undefined names. The settings are in ``pyproject.toml``.
