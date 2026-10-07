[![Tests](https://github.com/JonathanOrr/XPlane2Blender/actions/workflows/tests.yml/badge.svg?branch=develop)](https://github.com/JonathanOrr/XPlane2Blender/actions/workflows/tests.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Imports: isort](https://img.shields.io/badge/%20imports-isort-%231674b1?style=flat&labelColor=ef8336)](https://pycqa.github.io/isort/)

> **This is an unofficial community fork**, not affiliated with or supported by Laminar Research.
> It keeps XPlane2Blender working on current Blender releases (5.2 LTS). The official add-on is at
> [X-Plane/XPlane2Blender](https://github.com/X-Plane/XPlane2Blender). Please report problems with this
> fork [here](https://github.com/JonathanOrr/XPlane2Blender/issues), not to Laminar Research.

# Introduction
This addon for Blender 3.6 and up makes it possible to export models made in Blender to the X-Plane object format (.obj). 
This fork also has a full **importer** for X-Plane objects and whole aircraft, see [Importing](#importing-x-plane-aircraft-and-objects).

## Contact Us
The best way to contact us is through [a bug report](https://github.com/X-Plane/XPlane2Blender/issues). Otherwise, e-mail **ted at x-plane dot com**, especially if you're worried about the security of your models while we debug them.

## General Requirements
- Blender 3.6 or newer, with Blender 5.2 LTS recommended. Every push runs the test suite on Blender 3.6 LTS, 4.2 LTS, 4.5 LTS and 5.2 LTS, and 4.1 has been checked by hand
- For the greatest stability, use the latest non-beta version of [XPlane2Blender](https://github.com/X-Plane/XPlane2Blender/releases/latest)

For Blender 2.79 through 3.5, use the releases from the [official repository](https://github.com/X-Plane/XPlane2Blender/releases). The experimental Blender 2.49 converter also lives there and is not part of this fork.

## Automatic Installation
**Note: This process will override an existing copy of the plugin!** To backup your current version of the plugin, see the manual instructions in the [manual](https://xp2b-docs.gitbook.io/xplane2blender-docs/index-3/34_installation). **Always make backups of your work, especially when beta testing, as newer versions may not be backwards compatibility.** Read the release notes for more details.

1. Download the [addon](https://github.com/X-Plane/XPlane2Blender/releases/latest) with a name like ``io_xplane2blender_4_0_0-rc_1-89_20200910152046.zip``. **Do not download the .zip file called "Source Code", do not unzip the io_xplane2blender .zip file**
2. In Blender, open up the Preferences and go to the Add-ons tab. In Blender 4.2 and later, open the drop-down menu in the top right and click "Install from Disk...". In older versions, click "Install..." at the top
3. Using the file picker, find the .zip file and click "Install from Disk..." (or "Install Add-on"). This will automatically unzip to the addons folder
4. Ensure the checkbox next to the words "Import-Export: Export: X-Plane (.obj)" is checked
5. **Restart Blender even if you see the UI change**
6. Begin using XPlane2Blender!

For less stable betas or different versions see the [releases page](https://github.com/X-Plane/XPlane2Blender/releases). Be sure to read the notes.

## Get Started!
See the [Introduction to XPlane2Blender Video](https://developer.x-plane.com/tools/blender/) and download the example files and you'll be well on your way to exporting your first mesh and seeing it in X-Plane! Although the Blender version shown is Blender 2.79, XPlane2Blender is almost entirely the same across versions.

## Exporting Work In Progress
You can export at any stage: settings you have started but not filled in yet are left out of the OBJ instead of stopping the export, and the status bar counts them, for example `Exported 10 file(s); left out as unfinished: 61 light levels without a dataref`. The full list is in the `XPlane2Blender.log` text file. Today this covers light levels without a dataref (an empty one would write an invalid line) and meshes without a material (they export with X-Plane's default material state). A file with a real error is not written, but the other files of the export still are, and the status bar says which ones were skipped.

## Find And Replace, Duplicate And Replace
For the many controls that differ only by side or number. In the 3D viewport's sidebar (N), the **X-Plane** tab has a **Find and Replace** panel: add pairs such as `cockpit/mcdu/` → `cockpit/mcdu_2/` and `Captain` → `First Officer`, choose which settings to touch (commands, datarefs, light levels, tooltips, custom attributes) and which objects (selected, selected and their children, or the whole scene), and the panel previews every change before you apply it.
- **Find and Replace** changes the objects in place.
- **Duplicate and Replace** copies the selection, renames the settings on the copies only and lets you move them, like Shift+D. Copy the captain's MCDU once and the first officer's is done.
- Pairs are applied in order, **Match Case** is on by default (X-Plane names are case sensitive) and **Regex** allows regular expressions with `\1` groups.
- A material or light that objects outside the selection also use is left alone, so changing one side never changes the other. The panel says how many were skipped.
- Both are normal Blender operations: Ctrl+Z undoes them and the Adjust Last Operation panel works.

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
| Make Export Roots | Ticks each OBJ's collection as an XPlane2Blender root collection so Export OBJs writes it again. Off by default, because exporting a whole aircraft would write every file. The texture and export settings are always filled in, so you can tick a single collection later |
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
