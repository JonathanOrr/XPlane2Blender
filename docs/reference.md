# Settings Reference

Every setting, button and menu of the add-on's panels, under the name the panel shows, with its tooltip. Where a
setting only shows for some kinds of object, **Shown for** says which. The [guides](README.md) explain how they are
used.

<!-- Written by docs/tools/reference.py from the add-on itself. Do not edit by hand: run
     blender -b --factory-startup --python docs/tools/reference.py -->

## Object tab

### X-Plane

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| In cockpit.obj | button |  | Show this file's settings in the Scene tab's X-Plane Export panel |

### Clickable

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Clickable (on / off) | setting |  | If checked, this object will be treated as a manipulator |
| Kind Of Control | menu |  | Choices: Drag in two directions, Slide by dragging, Button, Drag runs commands, Push, Radio button, Step, Step and wrap around, Toggle, Blocks clicks, Drag the mouse sideways, Knob, two commands, Switch, up / down, two commands, Switch, left / right, two commands, Switch, up / down, Switch, left / right, Knob, Slide by dragging, with detents, Turn by dragging, Turn by dragging, with detents. |
| Left / right dataref | setting | Drag in two directions | Dataref 1 |
| Search | icon button | all but Blocks clicks, Slide by dragging, with detents, Turn by dragging, Turn by dragging, with detents | Search X-Plane's own list and the names this file already uses |
| Up / down dataref | setting | Drag in two directions | Dataref 2 |
| Drag width | setting | Drag in two directions | X-Drag axis length |
| Drag height | setting | Drag in two directions | Y-Drag axis length |
| Left / right from | setting | Drag in two directions | Value 1 min |
| Left / right to | setting | Drag in two directions | Value 1 max |
| Up / down from | setting | Drag in two directions | Value 2 min |
| Up / down to | setting | Drag in two directions | Value 2 max |
| Mouse wheel step | setting | Drag in two directions, Slide by dragging, Push, Radio button, Step, Step and wrap around, Toggle, Drag the mouse sideways, Turn by dragging | Value change on mouse wheel tick |
| Cursor | setting |  | The mouse cursor type when hovering over the object Choices: Four Arrows, Hand, Button, Rotate Small, Rotate Small Left, Rotate Small Right, Rotate Medium, Rotate Medium Left, Rotate Medium Right, Rotate Large, Rotate Large Left, Rotate Large Right, Up Down, Down, Up, Left Right, Left, Right, Arrow. |
| Tooltip | setting | all but Blocks clicks | The tooltip will be displayed when hovering over the object |
| Direction and values from the animation | setting | Slide by dragging | Use new algorithms to autodetect certain manipulator settings from animation data |
| Dataref | setting | Slide by dragging, Push, Radio button, Step, Step and wrap around, Toggle, Drag the mouse sideways, Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | Dataref 1 |
| Drag X | setting | Slide by dragging, Drag runs commands | X-Drag axis length |
| Drag Y | setting | Slide by dragging, Drag runs commands | Y-Drag axis length |
| Drag Z | setting | Slide by dragging, Drag runs commands | Z-Drag axis length |
| Value at start | setting | Slide by dragging | Value 1 |
| Value at end | setting | Slide by dragging | Value 2 |
| Command | setting | Button, Knob, Switch, up / down, Switch, left / right | The command to fire when manipulator is used |
| Forward command | setting | Drag runs commands | Positive command |
| Back command | setting | Drag runs commands | Negative command |
| Value while held | setting | Push | Value to set dataref on mouse down |
| Value when released | setting | Push | Value to set dataref on mouse up |
| Value when clicked | setting | Radio button | Value to set dataref on mouse down |
| Add on click | setting | Step, Step and wrap around | Value to set dataref on mouse down |
| Add while held | setting | Step, Step and wrap around | Value to set dataref on mouse hold |
| Lowest | setting | Step, Step and wrap around | Value 1 min |
| Highest | setting | Step, Step and wrap around | Value 1 max |
| On value | setting | Toggle | On value |
| Off value | setting | Toggle | Off value |
| Drag distance (pixels) | setting | Drag the mouse sideways | X-Drag axis length |
| Step | setting | Drag the mouse sideways | Dataref increment |
| Speed curve | setting | Drag the mouse sideways | Power of an exponential curve that controls the speed at which the dataref changes. Higher numbers cause a more “non-linear” response, where small drags are very precise and large drags are very fast |
| Lowest | setting | Drag the mouse sideways, Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | Value 1 |
| Highest | setting | Drag the mouse sideways, Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | Value 2 |
| Clockwise command | setting | Knob, two commands (command) | Positive command |
| Counter-clockwise command | setting | Knob, two commands (command) | Negative command |
| Up command | setting | Switch, up / down, two commands (command) | Positive command |
| Down command | setting | Switch, up / down, two commands (command) | Negative command |
| Right command | setting | Switch, left / right, two commands (command) | Positive command |
| Left command | setting | Switch, left / right, two commands (command) | Negative command |
| Step per click | setting | Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | Value change on click |
| Step while held | setting | Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | Value change on hold |
| Datarefs from the animation | setting | Slide by dragging, with detents, Turn by dragging, Turn by dragging, with detents | If checked, dataref(s) for this manipulator will be taken from its mesh's animations |
| Add Detent | button | Slide by dragging, with detents, Turn by dragging, with detents | Add an entry |
| Own detent dataref range | setting | Turn by dragging, with detents | Drag Rotate With Detents: the detent dataref goes from Value 2 Min to Value 2 Max as the lever is lifted (Laminar's levers use 0 to 1), and detent heights are in its units. Off: it goes from 0 to the lift in meters |

### Moves

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Button | button |  | Animate the selected objects as push buttons that move in while their command is held (CMND= dataref) |
| Switch | button |  | Animate the selected objects as switches with a number of positions, each a dataref value |
| Knob / Lever | button |  | Animate the selected objects as knobs, levers or sliders that follow a dataref over a range |
| Dataref Path | setting |  | Dataref Path |
| Search | icon button |  | Search X-Plane's own list and the names this file already uses |
| Remove Dataref | icon button |  | Remove this dataref and its keyframes |
| 0 | button |  | Go to this key to see or change the pose |
| 90 | button |  | Go to this key to see or change the pose |
| 180 | button |  | Go to this key to see or change the pose |
| 270 | button |  | Go to this key to see or change the pose |
| 360 | button |  | Go to this key to see or change the pose |
| At | setting |  | Value |
| Key Pose | button |  | Key where it is now at this dataref value: pose it, type the value, click. Keys are linear, like X-Plane |
| Repeats Every | setting |  | Loop amount of animation, useful for ever increasing Datarefs. A value of 0 will ignore this setting |
| Add Dataref | button |  | Add a dataref to the active object or bone |

### Shows / Hides

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Dataref Purpose | setting |  | Choices: Show, Hide. |
| Remove Dataref | icon button |  | Remove this dataref and its keyframes |
| Dataref Path | setting |  | Dataref Path |
| Search | icon button |  | Search X-Plane's own list and the names this file already uses |
| is from | setting |  | Show/Hide value 1 |
| to | setting |  | Show/Hide value 2 |
| Show When | button |  | Add a dataref to the active object or bone |
| Hide When | button |  | Add a dataref to the active object or bone |

### Glow

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Glow (on / off) | setting |  | If checked values will change the brightness of the _LIT texture for the object. This overrides the sim's decision about object lighting |
| Dataref | setting |  | The dataref is interpreted as a value between v1 and v2. Values outside v1 and v2 are clamped |
| Search | icon button |  | Search X-Plane's own list and the names this file already uses |
| Off At | setting |  | Value 1 for light level |
| Full At | setting |  | Value 2 for light level |
| Use Photometric Units | setting |  | Use brightness in nts in to change the _LIT texture |
| Full (nits) | setting |  | The brightness in nts of your _LIT texture at its brightest |

### Attachment Point

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Is A | setting |  | Type XPlane2Blender item this is Choices: None, Particle Emitter, Wheel, Magnet. |
| Emitter | setting |  | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Emitter Index Enabled | setting |  | Enables the emitter array index |
| Array Index | setting |  | The index in the emitter's array |
| Gear | setting |  |  |
| Wheel | setting |  |  |
| Name | setting |  | Human readable name for debugging purposes |
| Tablet | setting |  | Sets the type to include 'xpad' |
| Flashlight | setting |  | Sets the type to include 'flashlight' |

### Light

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Kind Of Light | menu |  | Choices: Library Light, Spill, Glow Sprite, Library Light, By Name, Library Light, Manual, Not Exported. |
| Name | setting | Library Light, Library Light, By Name, Library Light, Manual | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Choose X-Plane Light | icon button | Library Light, Library Light, By Name, Library Light, Manual | Choose a light from lights.txt. The list says whether each light is a spill (lights its surroundings) or a glow (a halo that lights nothing) |
| Preview As In X-Plane | button | all but Not Exported | Make lights look in the viewport the way X-Plane draws them: spills light their surroundings (custom spills out to their real reach), glows light nothing. Only settings the exporter never reads are changed |
| Reach (m) | setting | Spill | Size parameter for Custom Lights. For a Spill it is how far it reaches in meters (the Blender light's Custom Distance) |
| Brightness Dataref | setting | Spill | An X-Plane Dataref |
| Search | icon button | Spill, Glow Sprite | Search X-Plane's own list and the names this file already uses |
| Color | setting | Spill, Glow Sprite | Light color |
| Dim | setting | Spill | The alpha of a Spill: 1 is full brightness, 0 is off until its dataref brightens it |
| Size | setting | Glow Sprite | Size parameter for Custom Lights. For a Spill it is how far it reaches in meters (the Blender light's Custom Distance) |
| Left | setting | Glow Sprite | The texture coordinates in the following order: left,top,right,bottom (fractions from 0 to 1) |
| Top | setting | Glow Sprite | The texture coordinates in the following order: left,top,right,bottom (fractions from 0 to 1) |
| Right | setting | Glow Sprite | The texture coordinates in the following order: left,top,right,bottom (fractions from 0 to 1) |
| Bottom | setting | Glow Sprite | The texture coordinates in the following order: left,top,right,bottom (fractions from 0 to 1) |
| Dataref | setting | Glow Sprite | An X-Plane Dataref |
| Type The Color | setting | Glow Sprite | Used instead of the Blender color picker to input any RGB values. Useful for certain datarefs |
| Alpha | setting | Glow Sprite | The energy this light would emit over its entire area if it wasn't limited by the spot angle, in units of radiant power (W) |
| As Text | setting | Library Light, Manual | The additional parameters vary in number and definition based on the particular parameterized light selected |

### Light Lines

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Add Line | button |  | Add an entry |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| HUD Glass | setting |  | Object is the glass of a HUD display |
| Rain Cannot Escape | setting |  | Rain cannot escape from the object |
| Draw Order | setting |  | If checked you can override the internal weight of the object. Heavier objects will be written later in OBJ |
| Its Own File, From Its Own Origin | setting |  | Activate to export this object and all its children into it's own .obj file |
| Add Line | button |  | Add an entry |
| Add Animation Line | button |  | Add an entry |
| Order | setting | Draw Order on | Usual weights are: Meshes 0-8999, Lines 9000 - 9999, Lights > = 10000 |

## Material tab

### X-Plane

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Visible | setting |  | If turned off, objects with this material won't be drawn |
| Transparency | setting |  | Choices: Smooth, Hard Edge, Cut Shadow. |
| Casts Shadows | setting |  | If enabled, objects with this material cast shadows |
| Camera Cannot Pass Through | setting |  | X-Plane's camera will be prevented from moving through objects with this material. Only allowed in Cockpit type exports |
| Screen | setting |  | Choices: None, 2D Panel, Avionics. |
| Material Glow | setting |  | If checked values will change the brightness of the _LIT texture for objects with this material. This overrides the sim's decision about object lighting |
| Use Cockpit Panel Luminance | setting | all but screen: None | Use cockpit panel luminance feature |
| Max Brightness (nits) | setting | all but screen: None | Real world maximum brightness of the panel, in nts |
| Device | setting | all but screen: None, screen: Panel Texture | GPS device name Choices: GNS430_1, GNS430_2, GNS530_1, GNS530_2, CDU739_1, CDU739_2, G1000_PFD1, G1000_MFD, G1000_PFD2, CDU815_1, CDU815_2, Primus_PFD_1, Primus_PFD_2, Primus_MFD_1, Primus_MFD_2, Primus_MFD_3, Primus_RMU_1, Primus_RMU_2, MCDU_1, MCDU_2, Plugin Device. |
| Bus 1 | setting | all but screen: None, screen: Panel Texture | System bus 1 |
| Bus 2 | setting | all but screen: None, screen: Panel Texture | System bus 2 |
| Bus 3 | setting | all but screen: None, screen: Panel Texture | System bus 3 |
| Bus 4 | setting | all but screen: None, screen: Panel Texture | System bus 4 |
| Bus 5 | setting | all but screen: None, screen: Panel Texture | System bus 5 |
| Bus 6 | setting | all but screen: None, screen: Panel Texture | System bus 6 |
| Brightness Channel | setting | all but screen: None, screen: Panel Texture | The brightness knob of the screen: a 0 based index of X-Plane's lighting channels (rheostats), or -1 for none (Laminar's G1000 screens use it). Not affected by 'Light Level' |
| Brighter In Daylight | setting | all but screen: None, screen: Panel Texture | If true, the screen brightens automatically to be readable in the day. Otherwise it is 'washed out' in daylight |
| Cut Off Below | setting | transparency: Alpha Cutoff, transparency: Shadow | Levels in the texture below this level are rendered as fully transparent and levels above this level are fully opaque |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Hard Surface | setting |  | Controls the bumpiness of material in X-Plane Choices: None, Water, Concrete, Asphalt, Grass, Dirt, Gravel, Lakebed, Snow, Shoulder, Blastpad, Smooth. |
| Draw On Top | setting |  | Draws the surface on top of the ones under it (X-Plane's polygon offset), for decals and labels that flicker. Leave at 0 for default behaviour |
| Add Line | button |  | Add an entry |
| Can Be Under It (deck) | setting | hard surface | Allows the user to fly under the surface |

## Bone tab

### X-Plane

Nothing to set here in the demo scene.

### Moves

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Key By Hand | button |  | Add a dataref to the active object or bone |

### Shows / Hides

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Show When | button |  | Add a dataref to the active object or bone |
| Hide When | button |  | Add a dataref to the active object or bone |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Draw Order | setting |  | If checked you can override the internal weight of the object. Heavier objects will be written later in OBJ |
| Add Line | button |  | Add an entry |
| Add Animation Line | button |  | Add an entry |

## Collection tab

### X-Plane

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| X-Plane (on / off) | setting |  | Activate to export all this collection's children as an .obj file |
| Saved As | setting |  | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Type | setting |  | Choices: Aircraft Part, Cockpit. |
| File Settings And Export | button |  | Show this file's settings in the Scene tab's X-Plane Export panel |

## Scene tab

### X-Plane Export

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| New File From Selection | button |  | Make a new OBJ file holding the selected objects (and their children). They leave the files they were in |
| Save The .blend First | button |  | Exports OBJs relative to the .blend file |

### File

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Saved As | setting |  | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Type | setting |  | Choices: Aircraft Part, Cockpit. |
| Day | setting |  | Texture to use for objects on this layer |
| Night | setting |  | Night Texture to use for objects on this layer |
| Normal | setting |  | Normal/Specular Texture to use for objects on this layer |
| From Materials | button |  | Fill the file's empty texture slots with the images its materials use most. X-Plane draws a whole OBJ with one set of textures |
| See-Through Glass | setting |  | The alpha channel of the albedo (day texture) will be used to create translucent rendering |
| Metalness In Normal Map | setting |  | The normal map's blue channel will be used for base reflectance |
| Override Specular | setting |  | Write this file's GLOBAL_specular, the shininess every part has unless its material says otherwise, including screens and panels, and the materials' Specular where it differs. Off: each material writes its own, panels none, and with Metalness In Normal Map the file is fully shiny (1) |
| Specular (whole file) | setting |  | GLOBAL_specular: 0 to 1. With Metalness In Normal Map it scales the normal map's shine |
| Override Maximum Luminance | setting |  | Override maximum luminance for LIT texture |
| Max Glow (nits) | setting |  | The overriden maximum luminance value for the LIT texture, in nts |
| Levels | setting |  | Levels of detail Choices: None, 1, 2, 3, 4. |
| Panel Texture | setting | all but Aircraft (Part) file | Panel Texture Mode, affects all Materials using Panel Choices: Default, Emissive Panel Texture Only, Regions. |
| Regions | setting | panel texture: Regions | Number of Cockpit regions to use Choices: None, 1, 2, 3, 4. |
| Near | setting | two levels of detail | Near distance (inclusive) in meters |
| Far | setting | two levels of detail | Far distance (exclusive) in meters |

### X-Plane 12 Texture Maps

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Normal | setting |  | XY normal texture to use for objects on this layer |
| Material / Gloss | setting |  | Material/Gloss texture to use for objects on this layer |
| Gloss | setting |  | Gloss texture to use for objects on this layer |

### Rain, Defrost And Wipers

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Rain Scale | setting |  | Scales the visual output of rain to match texture resolution |
| Texture | setting |  | File path to the thermal texture |
| Pilot Front Windshield | setting |  |  |
| Copilot Front Windshield | setting |  |  |
| Pilot Side Window | setting |  |  |
| Copilot Side Window | setting |  |  |
| Gradient Texture | setting |  | File path to the wiper gradient texture (click 'Make Wiper Gradient Texture' to make) |
| Outside Glass | setting |  | Name of Object to be used as exterior glass (such as a Windshield) by the baker |
| Wiper 1 | setting |  |  |
| Start Frame | setting |  | Start of keyframe range for baking wiper gradient texture |
| Bake For cockpit.obj | button |  | Makes the Wiper Gradient Texture from the Rain Settings of the active collection (may take more than 30 minutes) |
| Seconds | setting | a defrost source and a wiper on | Defrost time in seconds (Can be a dataref) |
| On/Off Dataref | setting | a defrost source and a wiper on | Dataref that controls source on/off |
| Blade Object | setting | a defrost source and a wiper on | Name of wiper object, used in creation of wiper gradient texture |
| Dataref | setting | a defrost source and a wiper on | The dataref that controls the motion of the wiper object |
| From | setting | a defrost source and a wiper on | Start dataref value of Wiper animation |
| To | setting | a defrost source and a wiper on | End dataref value of Wiper animation |
| Blade Width | setting | a defrost source and a wiper on | Width of wiper as the percent of wiper animation arc that is covered by the blade at rest. Start low and increase until it looks right |
| Wiper 2 | setting | a defrost source and a wiper on |  |

### Detail Textures

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Detail 1 | setting |  | Detail Texture to use for objects on this layer |
| Detail 2 | setting |  | Detail Texture to use for objects on this layer |
| Normal Detail 1 | setting |  | Normal map detail texture to use for objects on this layer |
| Normal Detail 2 | setting |  | Normal map detail texture to use for objects on this layer |
| Modulator | setting |  | Modulator texture to use for objects on this layer |
| Projected | setting | a detail texture set | If checked, the detail texture will be projected |
| Scale | setting | a detail texture set | Scale of the detail texture |
| Red | setting | a detail texture set | Red channel key for the RGB part of the detail texture |
| Green | setting | a detail texture set | Green channel key for the RGB part of the detail texture |
| Blue | setting | a detail texture set | Blue channel key for the RGB part of the detail texture |
| Alpha | setting | a detail texture set | Alpha channel key for the RGB part of the detail texture |
| Modulator | setting | a detail texture set | Modulator strength for the RGB part of the detail texture |
| Constant | setting | a detail texture set | Constant strength for the RGB part of the detail texture |
| Red | setting | a detail texture set | Red channel key for the alpha part of the detail texture |
| Green | setting | a detail texture set | Green channel key for the alpha part of the detail texture |
| Blue | setting | a detail texture set | Blue channel key for the alpha part of the detail texture |
| Alpha | setting | a detail texture set | Alpha channel key for the alpha part of the detail texture |
| Modulator | setting | a detail texture set | Modulator strength for the alpha part of the detail texture |
| Constant | setting | a detail texture set | Constant strength for the alpha part of the detail texture |
| Preview In Viewport | button | a detail texture set | Show this file's detail textures on its materials in Material Preview, approximately as X-Plane draws them. Nothing exported changes |
| Preview Detail Textures | icon button | a detail texture set | Show this file's detail textures on its materials in Material Preview, approximately as X-Plane draws them. Nothing exported changes |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Particle Systems (.pss) | setting |  | Relative file path to a .pss that defines particles |
| Slung Load Weight (lb) | setting |  | Weight of the object in pounds, for use in the physics engine if the object is being carried by a plane or helicopter |
| Debug Info In This OBJ | setting |  | If this and the scene's Debug are checked, debug information for this OBJ will be written to the export log and the OBJ |
| Add Line | button |  | Add an entry |

### Options

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Smaller Files (share vertices) | setting |  | If checked file size will be optimized. However this can increase export time slightly |
| Debug Info | setting |  | If checked debug information will be printed to the console and into OBJ files |
| Developer Tools | setting |  | Tools for people working on this add-on itself |
| Enable Breakpoints | setting |  | Allows use of Eclipse breakpoints (must have PyDev, Eclipse installed and configured to use and Pydev Debug Server running!) |
| Dry Run | setting |  | Run exporter without actually writing .objs to disk |
| Export To Fixtures Folder | button |  | Exports OBJs relative to the .blend file |
| Apply the 'Material' datablock to all objects | button |  | Applies the 'Material' datablock to all without a material. If 'Material' does not exist, it will be created |
| Create Fixture Names From Roots | button |  | Changes each exportable root's Name property to 'test_' + root.name |
| Create lights.txt Summary | button |  | Create a text block listing all known lights and attributes about them |
| Fake XPlane2Blender Version | setting |  | The Fake XPlane2Blender Version to re-run the upgrader with |
| Re-run Updater | button |  | Re-runs the updater. This does not undo an update that happened on load! |

### X-Plane Unfinished Work

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Check | button | before Check | List what is not filled in yet in the export files. None of it stops an export |
| Check Again | button | after Check | List what is not filled in yet in the export files. None of it stops an export |

### X-Plane Tools

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Click Zones | setting |  | Outline what can be clicked in X-Plane: orange runs commands, blue sets datarefs, green is dragged |
| Click Labels | setting |  | Say what clicking each object does Choices: No Labels, Labels: Selected, Labels: All. |
| Preview Every Light As In X-Plane | button |  | Make lights look in the viewport the way X-Plane draws them: spills light their surroundings (custom spills out to their real reach), glows light nothing. Only settings the exporter never reads are changed |
| Tidy Empties And Light Cones | button |  | Draw empties and spot light cones as small as the parts hanging on them, so a crowded cockpit can be read and clicked. Only the viewport changes, nothing is exported differently |
| Open The X-Plane Workspace | button |  | Open the X-Plane workspace: the 3D View with the X-Plane overlays and lever handle, Properties on the Object tab. It is made from Layout the first time |

### X-Plane Find And Replace

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Find | setting |  | Text to find |
| Replace | setting |  | Text to put in its place |
| Remove Pair | icon button |  | Remove this find and replace pair |
| Add Pair | button |  | Add a find and replace pair |
| Swap Find And Replace | icon button |  | Swap Find And Replace in every pair, to go back the other way (right to left instead of left to right) |
| Objects | setting |  | Choices: Selected, Selected And Children, Whole Scene. |
| Settings | setting |  | Choices: Commands, Datarefs, Light Levels, Tooltips, Custom Attributes. |
| Match Case | setting |  | Datarefs and commands are case sensitive in X-Plane |
| Regex | setting |  | Read Find as a regular expression, Replace may use \1 for groups |
| Preview | setting |  |  |
| Find And Replace | button |  | Replace text in the X-Plane settings (commands, datarefs, light levels, tooltips, custom attributes) of many objects |
| Duplicate And Replace | button |  | Duplicate the selected objects and replace text in the X-Plane settings of the copies, then move them |

### X-Plane Tables

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Table | setting |  | Choices: Clickable, Glow, Datarefs, Lights. |
| Selected Only | setting |  | List only the selected objects |
| Select Listed | button |  | Select every object the list shows, the search box applied, to work on them together: copy settings, find and replace, hide or move them |
| Export CSV | button |  | Save the table as a CSV file for a spreadsheet |
| Import CSV | button |  | Read a CSV file and apply its values to the objects with the same names |

## In Blender's Own Menus

| Where | Item | Kind | What it does |
|---|---|---|---|
| File > Export | X-Plane Object (.obj) | button | Export to X-Plane Object file format (.obj) |
| File > Import | X-Plane Aircraft (.acf) | button | Import a whole X-Plane aircraft from its .acf file: every object, with textures, animations and manipulators |
| File > Import | X-Plane Object (.obj) | button | Import X-Plane objects (.obj), with their textures, animations and manipulators |
| Add (Shift+A) | X-Plane | menu |  |
| Right-click menu of the 3D View | X-Plane | menu |  |
| Overlays popover of the 3D View | Click Zones | setting | Outline what can be clicked in X-Plane: orange runs commands, blue sets datarefs, green is dragged |
| Overlays popover of the 3D View | Click Labels | setting | Say what clicking each object does Choices: No Labels, Labels: Selected, Labels: All. |
| Overlays popover of the 3D View | Motion | setting | Show how the selected animated objects move: their path from the first to the last keyframe, with the dataref value at each keyframe |
| Overlays popover of the 3D View | Lever Handle | setting | A handle on the active animated object: drag it to move the part through its animation the way it moves in X-Plane, and read the dataref value |
| Overlays popover of the 3D View | Lights | setting | Mark every X-Plane light in its color, with a tick for the way a spot shines, and name the selected ones and draw their cone. Blender draws a ground line and a circle of fixed size for every light, which is too much for hundreds of them: switch Overlays > Extras off to hide those (the lights still light the scene) |
| Overlays popover of the 3D View | Unfinished | setting | Outline in red what the last Check listed as not filled in yet |
| Workspace tabs' right-click menu | X-Plane Workspace | button | Open the X-Plane workspace: the 3D View with the X-Plane overlays and lever handle, Properties on the Object tab. It is made from Layout the first time |

## Import Options

The options in the side panel of the file browser.

| Where | Option | What it does |
|---|---|---|
| File > Import > X-Plane Aircraft (.acf) | Livery | Which set of textures to use |
| File > Import > X-Plane Aircraft (.acf) | Damage Objects | Also import the objects that only show when a part breaks |
| File > Import > X-Plane Aircraft (.acf) | Part Attached Objects | Also import objects attached to wings, gear or the body. They are placed at the aircraft origin |
| File > Import > X-Plane Aircraft (.acf) | Not Drawn Objects | Also show the objects the aircraft file flags as drawn nowhere, for example placeholders and easter eggs |
| File > Import > X-Plane Aircraft (.acf) | Textures and Materials | Load the texture images and build shader nodes so it looks like it does in X-Plane |
| File > Import > X-Plane Aircraft (.acf) | Animations | Create the dataref animations and show/hide settings, keyed on the parts themselves |
| File > Import > X-Plane Aircraft (.acf) | Manipulators | Set up the clickable manipulators on the meshes that have them |
| File > Import > X-Plane Aircraft (.acf) | Lights | Create X-Plane lights as Blender lights |
| File > Import > X-Plane Aircraft (.acf) | All LODs | Import every level of detail instead of only the first |
| File > Import > X-Plane Aircraft (.acf) | Mark What X-Plane Hides | Draw a sphere around the show/hide parts that X-Plane would not draw with the datarefs at their default values, and leave them out of renders. They stay visible and are exported like any part |
| File > Import > X-Plane Aircraft (.acf) | Make Export Files | Tick each imported OBJ's collection as an export file, so Export writes them again. Their texture and export settings are filled in either way, you can tick a single collection later |
| File > Import > X-Plane Aircraft (.acf) | Night Light Strength | How bright the _LIT texture glows. 0 shows the daytime look |
| File > Import > X-Plane Aircraft (.acf) | Light Strength | Switches the spill lights on, such as the cockpit annunciator and panel lights. They are dataref driven in X-Plane and off in the parked pose, so 0 keeps them from lighting the scene. 1 is the brightness the light's parameters ask for |
| File > Import > X-Plane Aircraft (.acf) | Scale | Multiplies all sizes. X-Plane uses meters, like Blender's default |
| File > Import > X-Plane Aircraft (.acf) | Show In Viewport | Switch the 3D viewport to the textured Material Preview, hide the dashed parent lines and frame everything. With many lights, Blender's own light gizmos are hidden (Overlays > Extras) and the X-Plane overlay marks the lights instead |
| File > Import > X-Plane Object (.obj) | Textures and Materials | Load the texture images and build shader nodes so it looks like it does in X-Plane |
| File > Import > X-Plane Object (.obj) | Animations | Create the dataref animations and show/hide settings, keyed on the parts themselves |
| File > Import > X-Plane Object (.obj) | Manipulators | Set up the clickable manipulators on the meshes that have them |
| File > Import > X-Plane Object (.obj) | Lights | Create X-Plane lights as Blender lights |
| File > Import > X-Plane Object (.obj) | All LODs | Import every level of detail instead of only the first |
| File > Import > X-Plane Object (.obj) | Mark What X-Plane Hides | Draw a sphere around the show/hide parts that X-Plane would not draw with the datarefs at their default values, and leave them out of renders. They stay visible and are exported like any part |
| File > Import > X-Plane Object (.obj) | Make Export Files | Tick each imported OBJ's collection as an export file, so Export writes them again. Their texture and export settings are filled in either way, you can tick a single collection later |
| File > Import > X-Plane Object (.obj) | Night Light Strength | How bright the _LIT texture glows. 0 shows the daytime look |
| File > Import > X-Plane Object (.obj) | Light Strength | Switches the spill lights on, such as the cockpit annunciator and panel lights. They are dataref driven in X-Plane and off in the parked pose, so 0 keeps them from lighting the scene. 1 is the brightness the light's parameters ask for |
| File > Import > X-Plane Object (.obj) | Scale | Multiplies all sizes. X-Plane uses meters, like Blender's default |
| File > Import > X-Plane Object (.obj) | Show In Viewport | Switch the 3D viewport to the textured Material Preview, hide the dashed parent lines and frame everything. With many lights, Blender's own light gizmos are hidden (Overlays > Extras) and the X-Plane overlay marks the lights instead |

## Menus

### Add (Shift+A) > X-Plane

| Item | Kind | What it does |
|---|---|---|
| Click Zone | button | Add an invisible box that can be clicked in X-Plane, at the 3D cursor |
| Light: Library Light | button | Add an X-Plane light at the 3D cursor |
| Light: Spill | button | Add an X-Plane light at the 3D cursor |
| Light: Glow Sprite | button | Add an X-Plane light at the 3D cursor |
| Wheel | button | Add an empty that X-Plane uses as a wheel, tablet mount or particle emitter, at the 3D cursor |
| Tablet Mount | button | Add an empty that X-Plane uses as a wheel, tablet mount or particle emitter, at the 3D cursor |
| Particle Emitter | button | Add an empty that X-Plane uses as a wheel, tablet mount or particle emitter, at the 3D cursor |

### Animate As

| Item | Kind | What it does |
|---|---|---|
| Push Button | button | Animate the selected objects as push buttons that move in while their command is held (CMND= dataref) |
| Switch | button | Animate the selected objects as switches with a number of positions, each a dataref value |
| Knob / Lever | button | Animate the selected objects as knobs, levers or sliders that follow a dataref over a range |

### Kind Of Control

| Item | Kind | What it does |
|---|---|---|
| Button | button | Make the selected objects clickable, as this kind of control |
| Switch, up / down | button | Make the selected objects clickable, as this kind of control |
| Switch, left / right | button | Make the selected objects clickable, as this kind of control |
| Knob | button | Make the selected objects clickable, as this kind of control |
| Switch, up / down, two commands | button | Make the selected objects clickable, as this kind of control |
| Switch, left / right, two commands | button | Make the selected objects clickable, as this kind of control |
| Knob, two commands | button | Make the selected objects clickable, as this kind of control |
| Drag runs commands | button | Make the selected objects clickable, as this kind of control |
| Toggle | button | Make the selected objects clickable, as this kind of control |
| Push | button | Make the selected objects clickable, as this kind of control |
| Radio button | button | Make the selected objects clickable, as this kind of control |
| Step | button | Make the selected objects clickable, as this kind of control |
| Step and wrap around | button | Make the selected objects clickable, as this kind of control |
| Knob | button | Make the selected objects clickable, as this kind of control |
| Switch, up / down | button | Make the selected objects clickable, as this kind of control |
| Switch, left / right | button | Make the selected objects clickable, as this kind of control |
| Turn by dragging | button | Make the selected objects clickable, as this kind of control |
| Turn by dragging, with detents | button | Make the selected objects clickable, as this kind of control |
| Slide by dragging | button | Make the selected objects clickable, as this kind of control |
| Slide by dragging, with detents | button | Make the selected objects clickable, as this kind of control |
| Drag in two directions | button | Make the selected objects clickable, as this kind of control |
| Drag the mouse sideways | button | Make the selected objects clickable, as this kind of control |
| Blocks clicks | button | Make the selected objects clickable, as this kind of control |

### Kind Of Light

| Item | Kind | What it does |
|---|---|---|
| Library Light | button | Set what kind of X-Plane light the selected lights are |
| Spill | button | Set what kind of X-Plane light the selected lights are |
| Glow Sprite | button | Set what kind of X-Plane light the selected lights are |
| Library Light, By Name | button | Set what kind of X-Plane light the selected lights are |
| Library Light, Manual | button | Set what kind of X-Plane light the selected lights are |
| Not Exported | button | Set what kind of X-Plane light the selected lights are |

### Move To File

| Item | Kind | What it does |
|---|---|---|
| cockpit.obj | button | Move the selected objects (and their children) into this file |
| exterior.obj | button | Move the selected objects (and their children) into this file |
| New File From Selection | button | Make a new OBJ file holding the selected objects (and their children). They leave the files they were in |

### Right-click > X-Plane

| Item | Kind | What it does |
|---|---|---|
| Kind Of Control | menu |  |
| Animate As Push Button | button | Animate the selected objects as push buttons that move in while their command is held (CMND= dataref) |
| Animate As Switch | button | Animate the selected objects as switches with a number of positions, each a dataref value |
| Animate As Knob / Lever | button | Animate the selected objects as knobs, levers or sliders that follow a dataref over a range |
| Move To File | menu |  |

### X-Plane Pie Menu (Shift+Q)

| Item | Kind | What it does |
|---|---|---|
| Kind Of Control | menu |  |
| Animate As | menu |  |
| Export | button | Exports OBJs relative to the .blend file |
| Click Zones | setting | Outline what can be clicked in X-Plane: orange runs commands, blue sets datarefs, green is dragged |
| Motion | setting | Show how the selected animated objects move: their path from the first to the last keyframe, with the dataref value at each keyframe |
| Lever Handle | setting | A handle on the active animated object: drag it to move the part through its animation the way it moves in X-Plane, and read the dataref value |
| Lights | setting | Mark every X-Plane light in its color, with a tick for the way a spot shines, and name the selected ones and draw their cone. Blender draws a ground line and a circle of fixed size for every light, which is too much for hundreds of them: switch Overlays > Extras off to hide those (the lights still light the scene) |
| Tidy Empties And Cones | button | Draw empties and spot light cones as small as the parts hanging on them, so a crowded cockpit can be read and clicked. Only the viewport changes, nothing is exported differently |
| Blender's Light Gizmos | setting | Object details, including empty wire, cameras and other visual guides |
| X-Plane | menu |  |
| Move To File | menu |  |
| Check | button | Check the export files for what is not filled in yet and outline it in red in the viewport |

### X-Plane Export Log Warning

Filled in from the scene (the export files, for example).
