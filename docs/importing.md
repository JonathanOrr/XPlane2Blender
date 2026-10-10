# Importing

**File > Import > X-Plane Aircraft (.acf)** brings in a whole aircraft from its `.acf` file: every object it lists, in
place, with its textures, materials, animations, click zones and lights. It reads the text `.acf` files of X-Plane 10,
11 and 12. **File > Import > X-Plane Object (.obj)** imports single OBJ files, several at once if you like. In Blender
4.1 and later you can also drop an `.acf` or `.obj` onto the 3D View.

## Options

The options are in the side panel of the file browser:

| Option | What it does |
|---|---|
| **Livery** | Uses the textures of one of the aircraft's liveries |
| **Damage Objects**, **Part Attached Objects** | Also brings in objects that are normally left out: they only show when a part breaks, or move with a wing or gear part |
| **Textures and Materials** | Loads the images and builds shader nodes, so it looks as it does in X-Plane |
| **Animations** | Creates the dataref animations and show / hide settings, keyed on the parts themselves |
| **Manipulators** | Makes the clickable parts clickable, with their commands, datarefs and tooltips |
| **Lights** | Creates the lights, see below |
| **All LODs** | Imports every level of detail instead of only the first. A file with one level of detail keeps its distances either way |
| **Mark What X-Plane Hides** | Draws a sphere around the parts X-Plane would not draw with the datarefs at their default values, and leaves them out of renders. They stay visible and are exported like any part: in Blender, hidden objects are never exported |
| **Make Export Files** | Ticks each OBJ's collection as an export file. Off by default, because exporting would then write every file of the aircraft; the files are listed unticked in the **Scene tab**'s **X-Plane Export**, so one tick exports one again |
| **Night Light Strength** | How much the night (LIT) texture glows, 0 shows the daytime look |
| **Light Strength** | Switches the spill lights on (annunciators, panel lights). 0 keeps them dark, as they are in the parked pose |
| **Scale** | Multiplies all sizes |
| **Show In Viewport** | Switches the 3D View to Material Preview and frames everything |

## What You Get

- Each OBJ becomes a collection, grouped under the aircraft's collection. The scene opens in the parked pose (gear
  down, flaps in and so on).
- An object set to "Prefill Only" in Plane Maker only hides the clouds behind it, and X-Plane never draws it. Its
  collection is named `... (prefill only, not drawn)`, for example the grey shell inside an airliner's cabin. It is
  still exported, under its own file name.
- The parts carry their own animations: the pivot is the part's origin and the dataref and keys are on the part, so a
  knob is one object you select and click. An Empty is only made where one is needed, for example a ` frame` Empty
  holding the tilt of a panel, so that the keys of every button in it are along the panel's own axes.
- Keys are linear, as in X-Plane, from frame 1 on.
- Each mesh with its own click zone, glow or material is a separate object with one material, so everything can be
  edited and exported again.
- Header lines the add-on has settings for fill them in: rain, defrost and wipers, the night texture's brightness,
  cockpit regions. Lines it has no setting for are kept as extra OBJ lines, or reported, never silently dropped.

## How Lights Come In

lights.txt gives a light a glow (a visible halo that lights nothing) and / or a spill (it lights its surroundings).
Spills become Blender point or spot lights with the cone, direction and power of the X-Plane light; glows are kept for
export but light nothing in Blender. The power is chosen for a plausible picture, and the exporter never reads it for
library lights and spills, so you can change it freely. With 20 or more lights the import hides Blender's own light
drawing and turns on the X-Plane **Lights** overlay, see [Lights](lights.md#seeing-them-in-the-3d-view).

## Limits

- Wings and fuselages that Plane Maker builds itself, not from OBJ files, are not imported.
- Objects attached to a wing, gear or body part are skipped unless **Part Attached Objects** is ticked; they are then
  placed at the aircraft's origin.
- Textures in the BC6 and BC7 DDS formats cannot be read by Blender, those materials have no image.
- Imported textures are linked by their full path: keep the aircraft where it is, or relink them in Blender.
