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
| Clickable (on / off) | setting |  | Make the object clickable in X-Plane |
| Kind Of Control | menu |  | Choices: Drag in two directions, Slide by dragging, Button, Drag runs commands, Push, Radio button, Step, Step and wrap around, Toggle, Blocks clicks, Drag the mouse sideways, Knob, two commands, Switch, up / down, two commands, Switch, left / right, two commands, Switch, up / down, Switch, left / right, Knob, Slide by dragging, with detents, Turn by dragging, Turn by dragging, with detents. |
| Left / right dataref | setting | Drag in two directions | The dataref the control changes (the left / right one in Drag in two directions) |
| Search | icon button | all but Blocks clicks, Slide by dragging, with detents, Turn by dragging, Turn by dragging, with detents | Search X-Plane's own list and the names this file already uses |
| Up / down dataref | setting | Drag in two directions | The second dataref: the up / down one in Drag in two directions, or the one the lever is lifted by for detents |
| Drag width | setting | Drag in two directions | How far the drag goes: along X in meters for a slide or Drag runs commands, the width of Drag in two directions, or the pixels of Drag the mouse sideways |
| Drag height | setting | Drag in two directions | How far the drag goes: along Y in meters for a slide or Drag runs commands, or the height of Drag in two directions |
| Left / right from | setting | Drag in two directions | The lowest value of a Step, or where the left / right dataref starts in Drag in two directions |
| Left / right to | setting | Drag in two directions | The highest value of a Step, or where the left / right dataref ends in Drag in two directions |
| Up / down from | setting | Drag in two directions | Where the up / down dataref starts in Drag in two directions, or the detent dataref with the lever at rest |
| Up / down to | setting | Drag in two directions | Where the up / down dataref ends in Drag in two directions, or the detent dataref with the lever lifted |
| Mouse wheel step | setting | Drag in two directions, Slide by dragging, Push, Radio button, Step, Step and wrap around, Toggle, Drag the mouse sideways, Turn by dragging | How much one click of the mouse wheel changes the dataref. 0: the wheel does nothing |
| Cursor | setting |  | The mouse cursor X-Plane shows over the object Choices: Four Arrows, Hand, Button, Rotate Small, Rotate Small Left, Rotate Small Right, Rotate Medium, Rotate Medium Left, Rotate Medium Right, Rotate Large, Rotate Large Left, Rotate Large Right, Up Down, Down, Up, Left Right, Left, Right, Arrow. |
| Tooltip | setting | all but Blocks clicks | The text X-Plane shows while the mouse is over the object |
| Direction and values from the animation | setting | Slide by dragging | Take the drag direction and the dataref values from the object's animation, instead of typing them in |
| Dataref | setting | Slide by dragging, Push, Radio button, Step, Step and wrap around, Toggle, Drag the mouse sideways, Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | The dataref the control changes (the left / right one in Drag in two directions) |
| Drag X | setting | Slide by dragging, Drag runs commands | How far the drag goes: along X in meters for a slide or Drag runs commands, the width of Drag in two directions, or the pixels of Drag the mouse sideways |
| Drag Y | setting | Slide by dragging, Drag runs commands | How far the drag goes: along Y in meters for a slide or Drag runs commands, or the height of Drag in two directions |
| Drag Z | setting | Slide by dragging, Drag runs commands | How far the drag goes along Z, in meters, for a slide or Drag runs commands |
| Value at start | setting | Slide by dragging | The dataref value at the start of the drag, or the lowest value of a stepped switch or knob |
| Value at end | setting | Slide by dragging | The dataref value at the end of the drag, or the highest value of a stepped switch or knob |
| Command | setting | Button, Knob, Switch, up / down, Switch, left / right | The command X-Plane runs when the object is clicked (for a Button, while it is held) |
| Forward command | setting | Drag runs commands | The command for one way: clockwise, up, right or forward |
| Back command | setting | Drag runs commands | The command for the other way: counter-clockwise, down, left or back |
| Value while held | setting | Push | The value the dataref is set to when the object is clicked (and held, for Push), or added on each click for a Step |
| Value when released | setting | Push | The value the dataref is set to when the mouse is released |
| Value when clicked | setting | Radio button | The value the dataref is set to when the object is clicked (and held, for Push), or added on each click for a Step |
| Add on click | setting | Step, Step and wrap around | The value the dataref is set to when the object is clicked (and held, for Push), or added on each click for a Step |
| Add while held | setting | Step, Step and wrap around | The value added to the dataref while the mouse is held down |
| Lowest | setting | Step, Step and wrap around | The lowest value of a Step, or where the left / right dataref starts in Drag in two directions |
| Highest | setting | Step, Step and wrap around | The highest value of a Step, or where the left / right dataref ends in Drag in two directions |
| On value | setting | Toggle | The dataref value when the toggle is on |
| Off value | setting | Toggle | The dataref value when the toggle is off |
| Drag distance (pixels) | setting | Drag the mouse sideways | How far the drag goes: along X in meters for a slide or Drag runs commands, the width of Drag in two directions, or the pixels of Drag the mouse sideways |
| Step | setting | Drag the mouse sideways | The dataref changes in steps of this size |
| Speed curve | setting | Drag the mouse sideways | How the dataref speeds up with the drag: higher numbers make small drags precise and large drags fast. 1: even |
| Lowest | setting | Drag the mouse sideways, Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | The dataref value at the start of the drag, or the lowest value of a stepped switch or knob |
| Highest | setting | Drag the mouse sideways, Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | The dataref value at the end of the drag, or the highest value of a stepped switch or knob |
| Clockwise command | setting | Knob, two commands (command) | The command for one way: clockwise, up, right or forward |
| Counter-clockwise command | setting | Knob, two commands (command) | The command for the other way: counter-clockwise, down, left or back |
| Up command | setting | Switch, up / down, two commands (command) | The command for one way: clockwise, up, right or forward |
| Down command | setting | Switch, up / down, two commands (command) | The command for the other way: counter-clockwise, down, left or back |
| Right command | setting | Switch, left / right, two commands (command) | The command for one way: clockwise, up, right or forward |
| Left command | setting | Switch, left / right, two commands (command) | The command for the other way: counter-clockwise, down, left or back |
| Step per click | setting | Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | How much each click changes the dataref |
| Step while held | setting | Switch, up / down (dataref), Switch, left / right (dataref), Knob (dataref) | How much the dataref changes while the mouse is held down |
| Datarefs from the animation | setting | Slide by dragging, with detents, Turn by dragging, Turn by dragging, with detents | Use the datarefs the object's animation is keyed on, instead of typing them in |
| Add Detent | button | Slide by dragging, with detents, Turn by dragging, with detents | Add a detent: a range where the lever moves freely, and how high it is lifted to get in |
| Own detent dataref range | setting | Turn by dragging, with detents | The detent dataref goes from its value at rest to its value lifted as the lever is lifted (Laminar's levers use 0 to 1), and the detent heights are in its units. Off: it goes from 0 to the lift in meters |

### Moves

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Button | button |  | Animate the selected objects as push buttons that move in while their command is held (CMND= dataref) |
| Switch | button |  | Animate the selected objects as switches with a number of positions, each a dataref value |
| Knob / Lever | button |  | Animate the selected objects as knobs, levers or sliders that follow a dataref over a range |
| Dataref Path | setting |  | The dataref, such as sim/cockpit2/switches/landing_lights_on, or name[0] for an array |
| Search | icon button |  | Search X-Plane's own list and the names this file already uses |
| Remove Dataref | icon button |  | Remove this dataref and its keyframes |
| 0 | button |  | Go to this key to see or change the pose |
| 90 | button |  | Go to this key to see or change the pose |
| 180 | button |  | Go to this key to see or change the pose |
| 270 | button |  | Go to this key to see or change the pose |
| 360 | button |  | Go to this key to see or change the pose |
| At | setting |  | The dataref value of this key |
| Key Pose | button |  | Key where it is now at this dataref value: pose it, type the value, click. Keys are linear, like X-Plane |
| Repeats Every | setting |  | Repeat the animation every this much of the dataref, for datarefs that keep growing (a turning propeller). 0: no repeat |
| Add Dataref | button |  | Add a dataref that moves it: pose it and key the pose at dataref values |

### Shows / Hides

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Dataref Purpose | setting |  | Choices: Show, Hide. |
| Remove Dataref | icon button |  | Remove this dataref and its keyframes |
| Dataref Path | setting |  | The dataref, such as sim/cockpit2/switches/landing_lights_on, or name[0] for an array |
| Search | icon button |  | Search X-Plane's own list and the names this file already uses |
| is from | setting |  | The lowest dataref value of the range |
| to | setting |  | The highest dataref value of the range |
| Show When | button |  | Show it only while a dataref is in a range |
| Hide When | button |  | Hide it while a dataref is in a range |

### Glow

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Glow (on / off) | setting |  | The night (LIT) texture's brightness follows a dataref, for this object only, instead of X-Plane's own lighting |
| Dataref | setting |  | The dataref the glow follows, from Off At to Full At. Values beyond them count as the nearest one |
| Search | icon button |  | Search X-Plane's own list and the names this file already uses |
| Off At | setting |  | The dataref value where the glow is off |
| Full At | setting |  | The dataref value where the glow is full |
| Use Photometric Units | setting |  | Give the brightness in nits (cd/m²) |
| Full (nits) | setting |  | How bright the night (LIT) texture is at its brightest, in nits (cd/m²) |

### Attachment Point

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Is A | setting |  | What X-Plane uses the empty for Choices: None, Particle Emitter, Wheel, Magnet. |
| Emitter | setting |  | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Emitter Index Enabled | setting |  | The emitter is one of an array of them, with an index |
| Array Index | setting |  | Which emitter of the array this is |
| Gear | setting |  | Which landing gear of the aircraft, as numbered in Plane Maker |
| Wheel | setting |  | Which wheel of that gear |
| Name | setting |  | A name for it in X-Plane's debug output |
| Tablet | setting |  | A mount for X-Plane's VR tablet |
| Flashlight | setting |  | A mount for X-Plane's VR flashlight |

### Light

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Kind Of Light | menu |  | Choices: Library Light, Spill, Glow Sprite, Library Light, By Name, Library Light, Manual, Not Exported. |
| Name | setting | Library Light, Library Light, By Name, Library Light, Manual | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Choose X-Plane Light | icon button | Library Light, Library Light, By Name, Library Light, Manual | Choose a light from lights.txt. The list says whether each light is a spill (lights its surroundings) or a glow (a halo that lights nothing) |
| Preview As In X-Plane | button | all but Not Exported | Make lights look in the viewport the way X-Plane draws them: spills light their surroundings (custom spills out to their real reach), glows light nothing. Only settings the exporter never reads are changed |
| Reach (m) | setting | Spill | A Spill's reach in meters (the Blender light's Custom Distance), or a Glow Sprite's size |
| Brightness Dataref | setting | Spill | The dataref that switches or dims the light |
| Search | icon button | Spill, Glow Sprite | Search X-Plane's own list and the names this file already uses |
| Color | setting | Spill, Glow Sprite | Light color |
| Dim | setting | Spill | The alpha of a Spill: 1 is full brightness, 0 is off until its dataref brightens it |
| Size | setting | Glow Sprite | A Spill's reach in meters (the Blender light's Custom Distance), or a Glow Sprite's size |
| Left | setting | Glow Sprite | The part of the texture the glow is drawn from: left, top, right and bottom, from 0 to 1 |
| Top | setting | Glow Sprite | The part of the texture the glow is drawn from: left, top, right and bottom, from 0 to 1 |
| Right | setting | Glow Sprite | The part of the texture the glow is drawn from: left, top, right and bottom, from 0 to 1 |
| Bottom | setting | Glow Sprite | The part of the texture the glow is drawn from: left, top, right and bottom, from 0 to 1 |
| Dataref | setting | Glow Sprite | The dataref that switches or dims the light |
| Type The Color | setting | Glow Sprite | Type the color as numbers instead of picking it, for values outside 0 to 1 (some halos use -1) |
| Alpha | setting | Glow Sprite | The energy this light would emit over its entire area if it wasn't limited by the spot angle, in units of radiant power (W) |
| As Text | setting | Library Light, Manual | The light's parameters, in the order lights.txt gives them for this light |

### Light Lines

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Add Line | button |  | Add an OBJ line typed by hand, for anything without a setting of its own |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| HUD Glass | setting |  | The object is the glass of a head-up display (HUD) |
| Rain Cannot Escape | setting |  | Rain does not run from this object onto the parts around it (TRIS_break) |
| Override Weight | setting |  | Choose where the object is written in the OBJ: heavier objects are written, and drawn, later |
| Draw Order | setting |  | Heavier is written later. Meshes are usually 0 to 8999, lines 9000 to 9999 and lights 10000 and up |
| Its Own File, From Its Own Origin | setting |  | Export this object and its children as their own OBJ file, from the object's origin |
| Add Line | button |  | Add an OBJ line typed by hand, for anything without a setting of its own |
| Add Animation Line | button |  | Add an OBJ line typed by hand that is written with the object's animation |

## Material tab

### X-Plane

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Visible | setting |  | Draw the surface. Off: it is not drawn but can still be clicked, for invisible click zones |
| Casts Shadows | setting |  | Objects with this material cast shadows |
| Camera Cannot Pass Through | setting |  | X-Plane's camera cannot pass through the surface. Cockpit files only |
| Transparency: | setting |  | Choices: Smooth, Hard Edge, Cut Shadow. |
| Screen: | setting |  | Choices: None, 2D Panel, Avionics. |
| Material Glow | setting |  | The night (LIT) texture's brightness follows a dataref, for every object with this material, instead of X-Plane's own lighting |
| Use Cockpit Panel Luminance | setting | all but screen: None | Give the screen a real-world brightness |
| Max Brightness (nits) | setting | all but screen: None | The screen's real-world brightness at its brightest, in nits (cd/m²) |
| Device | setting | all but screen: None, screen: Panel Texture | Which of X-Plane's avionics devices the screen shows Choices: GNS430_1, GNS430_2, GNS530_1, GNS530_2, CDU739_1, CDU739_2, G1000_PFD1, G1000_MFD, G1000_PFD2, CDU815_1, CDU815_2, Primus_PFD_1, Primus_PFD_2, Primus_MFD_1, Primus_MFD_2, Primus_MFD_3, Primus_RMU_1, Primus_RMU_2, MCDU_1, MCDU_2, Plugin Device. |
| Bus 1 | setting | all but screen: None, screen: Panel Texture | Electrical bus 1 powers the screen |
| Bus 2 | setting | all but screen: None, screen: Panel Texture | Electrical bus 2 powers the screen |
| Bus 3 | setting | all but screen: None, screen: Panel Texture | Electrical bus 3 powers the screen |
| Bus 4 | setting | all but screen: None, screen: Panel Texture | Electrical bus 4 powers the screen |
| Bus 5 | setting | all but screen: None, screen: Panel Texture | Electrical bus 5 powers the screen |
| Bus 6 | setting | all but screen: None, screen: Panel Texture | Electrical bus 6 powers the screen |
| Brightness Channel | setting | all but screen: None, screen: Panel Texture | The brightness knob of the screen: a 0 based index of X-Plane's lighting channels (rheostats), or -1 for none (Laminar's G1000 screens use it). Material Glow does not change it |
| Brighter In Daylight | setting | all but screen: None, screen: Panel Texture | The screen brightens by itself to be readable in daylight. Off: it looks washed out in daylight |
| Cut Off Below | setting | transparency: Alpha Cutoff, transparency: Shadow | Alpha below this is not drawn, alpha above it is opaque |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Hard Surface | setting |  | The aircraft can stand on the surface, and what kind it is (which sets its bumpiness). None: not solid Choices: None, Water, Concrete, Asphalt, Grass, Dirt, Gravel, Lakebed, Snow, Shoulder, Blastpad, Smooth. |
| Draw On Top | setting |  | Draws the surface over others at the same place (X-Plane's polygon offset), for decals and labels that flicker. 0: off |
| Add Line | button |  | Add an OBJ line typed by hand, for anything without a setting of its own |
| Can Be Under It (deck) | setting | hard surface | The aircraft can also be under the surface, as under a deck |

## Bone tab

### X-Plane

Nothing to set here in the demo scene.

### Moves

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Key By Hand | button |  | Add a dataref that moves it: pose it and key the pose at dataref values |

### Shows / Hides

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Show When | button |  | Show it only while a dataref is in a range |
| Hide When | button |  | Hide it while a dataref is in a range |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Override Weight | setting |  | Choose where the object is written in the OBJ: heavier objects are written, and drawn, later |
| Draw Order | setting |  | Heavier is written later. Meshes are usually 0 to 8999, lines 9000 to 9999 and lights 10000 and up |
| Add Line | button |  | Add an OBJ line typed by hand, for anything without a setting of its own |
| Add Animation Line | button |  | Add an OBJ line typed by hand that is written with the object's animation |

## Collection tab

### X-Plane

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| X-Plane (on / off) | setting |  | Export everything in this collection as one OBJ file |
| Saved As | setting |  | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Type: | setting |  | Choices: Aircraft Part, Cockpit. |
| File Settings And Export | button |  | Show this file's settings in the Scene tab's X-Plane Export panel |

## Scene tab

### X-Plane Export

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| New File From Selection | button |  | Make a new OBJ file holding the selected objects (and their children). They leave the files they were in |
| Save The .blend First | button |  | Export the ticked files next to the .blend file, or below it at their Saved As paths |

### File

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Saved As | setting |  | Unique name used in the code and scripting, can be re-defined in Python sub-classes if needed |
| Type: | setting |  | Choices: Aircraft Part, Cockpit. |
| Day | setting |  | TEXTURE: the color (albedo) texture of every part of the file |
| Night | setting |  | TEXTURE_LIT: the texture that glows at night, drawn over the day texture |
| Normal And Shine | setting |  | How the file's normal map and shine are textured Choices: One Texture, Normal + Metal / Gloss Maps, Normal + Gloss Maps. |
| Normal | setting | all but normal and shine: Normal + Metal / Gloss Maps, normal and shine: Normal + Gloss Maps | TEXTURE_NORMAL: the normal map, with the gloss in its alpha |
| From Materials | button |  | Fill the file's empty texture slots with the images its materials use most. X-Plane draws a whole OBJ with one set of textures |
| See-Through Glass | setting |  | Draw the file as see-through glass, as clear as the day texture's alpha |
| Metalness In Normal Map | setting |  | The normal map's blue is the metalness (base reflectance) |
| Override Specular | setting |  | Write this file's GLOBAL_specular, the shininess every part has unless its material says otherwise, including screens and panels, and the materials' Specular where it differs. Off: each material writes its own, panels none, and with Metalness In Normal Map the file is fully shiny (1) |
| Specular (whole file) | setting |  | GLOBAL_specular: 0 to 1. With Metalness In Normal Map it scales the normal map's shine |
| Override Maximum Luminance | setting |  | Set the brightest the night (LIT) texture gets |
| Max Glow (nits) | setting |  | The brightest the night (LIT) texture gets, in nits (cd/m²) |
| Levels | setting |  | How many levels of detail the file has: each draws its objects between two distances Choices: None, 1, 2, 3, 4. |
| Panel Texture | setting | all but Aircraft (Part) file | What the 2D panel screens of the file show Choices: Default, Emissive Panel Texture Only, Regions. |
| Regions | setting | panel texture: Regions | How many regions of the panel texture the screens use Choices: None, 1, 2, 3, 4. |
| Normal | setting | normal and shine: Normal + Metal / Gloss Maps, normal and shine: Normal + Gloss Maps | TEXTURE_MAP normal: the normal map, in red and green |
| Metal / Gloss | setting | normal and shine: Normal + Metal / Gloss Maps | TEXTURE_MAP material_gloss: the metalness in red and the gloss in green |
| Gloss | setting | normal and shine: Normal + Gloss Maps | TEXTURE_MAP gloss: the gloss, in red |
| Near | setting | two levels of detail | Drawn from this distance, in meters |
| Far | setting | two levels of detail | Drawn up to this distance, in meters |

### Rain, Defrost And Wipers

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Rain Scale | setting |  | Scales the rain drops to suit the resolution of the textures |
| Texture | setting |  | The defrost texture, which marks the area each window heat clears |
| Pilot Front Windshield | setting |  | The pilot front windshield is heated against frost |
| Copilot Front Windshield | setting |  | The copilot front windshield is heated against frost |
| Pilot Side Window | setting |  | The pilot side window is heated against frost |
| Copilot Side Window | setting |  | The copilot side window is heated against frost |
| Gradient Texture | setting |  | The wiper gradient texture, which Bake For makes |
| Outside Glass | setting |  | The outside glass the wipers sweep (such as the windshield), for the baker |
| Wiper 1 | setting |  | Export this wiper. The wipers are numbered from the first |
| Start Frame | setting |  | The first frame of the wiper animation to bake. The bake uses 255 frames |
| Bake For cockpit.obj | button |  | Bake the file's wiper gradient texture from the wipers' animation. It can take more than 30 minutes |
| Seconds | setting | a defrost source and a wiper on | How many seconds it takes to clear the window, or a dataref that gives it |
| On/Off Dataref | setting | a defrost source and a wiper on | The dataref that switches the window heat on and off |
| Blade Object | setting | a defrost source and a wiper on | The wiper blade object, whose sweep the gradient texture is baked from |
| Dataref | setting | a defrost source and a wiper on | The dataref that moves the wiper |
| From | setting | a defrost source and a wiper on | The dataref value where the wiper's sweep starts |
| To | setting | a defrost source and a wiper on | The dataref value where the wiper's sweep ends |
| Blade Width | setting | a defrost source and a wiper on | Width of wiper as the percent of wiper animation arc that is covered by the blade at rest. Start low and increase until it looks right |
| Wiper 2 | setting | a defrost source and a wiper on | Export this wiper. The wipers are numbered from the first |

### Detail Textures

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Detail 1 | setting |  | A detail texture, repeated over the day texture for fine detail up close |
| Detail 2 | setting |  | A detail texture, repeated over the day texture for fine detail up close |
| Normal Detail 1 | setting |  | A normal map detail texture, repeated over the normal map |
| Normal Detail 2 | setting |  | A normal map detail texture, repeated over the normal map |
| Modulator | setting |  | A texture whose red sets, part by part, how strongly the detail textures show |
| Projected | setting | a detail texture set | Project the detail texture by position instead of the UVs |
| Scale | setting | a detail texture set | How many times the detail texture repeats across the day texture |
| Red | setting | a detail texture set | How much the day texture's red adds to the strength, for the RGB part of the detail texture |
| Green | setting | a detail texture set | How much the day texture's green adds to the strength, for the RGB part of the detail texture |
| Blue | setting | a detail texture set | How much the day texture's blue adds to the strength, for the RGB part of the detail texture |
| Alpha | setting | a detail texture set | How much the day texture's alpha adds to the strength, for the RGB part of the detail texture |
| Modulator | setting | a detail texture set | How much the modulator texture adds to the strength, for the RGB part of the detail texture |
| Constant | setting | a detail texture set | The strength added everywhere, for the RGB part of the detail texture |
| Red | setting | a detail texture set | How much the day texture's red adds to the strength, for the alpha part of the detail texture |
| Green | setting | a detail texture set | How much the day texture's green adds to the strength, for the alpha part of the detail texture |
| Blue | setting | a detail texture set | How much the day texture's blue adds to the strength, for the alpha part of the detail texture |
| Alpha | setting | a detail texture set | How much the day texture's alpha adds to the strength, for the alpha part of the detail texture |
| Modulator | setting | a detail texture set | How much the modulator texture adds to the strength, for the alpha part of the detail texture |
| Constant | setting | a detail texture set | The strength added everywhere, for the alpha part of the detail texture |
| Preview In Viewport | button | a detail texture set | Show this file's detail textures on its materials in Material Preview, approximately as X-Plane draws them. Nothing exported changes |
| Preview Detail Textures | icon button | a detail texture set | Show this file's detail textures on its materials in Material Preview, approximately as X-Plane draws them. Nothing exported changes |

### Advanced

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Particles (.pss) | setting |  | The particle system file (.pss) the file's emitters use |
| Slung Load Weight (lb) | setting |  | Weight of the object in pounds, for use in the physics engine if the object is being carried by a plane or helicopter |
| Debug Info In This OBJ | setting |  | With the scene's Debug Info on, write debug comments into this OBJ and the export log |
| Add Line | button |  | Add an OBJ line typed by hand, for anything without a setting of its own |

### Options

| Name | Kind | Shown for | What it does |
|---|---|---|---|
| Smaller Files (share vertices) | setting |  | Write each vertex once per file, for smaller OBJs. Normals that differ only by Blender's rounding are merged |
| Debug Info | setting |  | Write debug comments into the OBJs, and debug information to the console |
| Developer Tools | setting |  | Tools for people working on this add-on itself |
| Enable Breakpoints | setting |  | Stop at breakpoints in a running PyDev debug server (Eclipse with PyDev) |
| Dry Run | setting |  | Run the export without writing the OBJs |
| Export To Fixtures Folder | button |  | Export the ticked files into fixtures |
| Apply the 'Material' datablock to all objects | button |  | Give every object without a material the material named 'Material', made if missing |
| Create Fixture Names From Roots | button |  | Name each export file 'test_' and its collection or object name |
| Create lights.txt Summary | button |  | Create a text block listing all known lights and attributes about them |
| Fake XPlane2Blender Version | setting |  | Re-run the updater as if the file was last saved by this version |
| Re-run Updater | button |  | Run the updater again. It does not undo an update made when the file was opened |

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
| File > Import > X-Plane Aircraft (.acf) | Show In Viewport | Switch the 3D viewport to the textured Material Preview, hide the dashed parent lines and frame everything. With many lights, Blender's own light gizmos are hidden (Overlays > Extras) and the X-Plane overlay marks the lights instead |
| File > Import > X-Plane Aircraft (.acf) | Night Light Strength | How bright the night (LIT) texture glows. 0 shows the daytime look |
| File > Import > X-Plane Aircraft (.acf) | Light Strength | Switches the spill lights on, such as the cockpit annunciator and panel lights. They are dataref driven in X-Plane and off in the parked pose, so 0 keeps them from lighting the scene. 1 is the brightness the light's parameters ask for |
| File > Import > X-Plane Aircraft (.acf) | Scale | Multiplies all sizes. X-Plane uses meters, like Blender's default |
| File > Import > X-Plane Object (.obj) | Textures and Materials | Load the texture images and build shader nodes so it looks like it does in X-Plane |
| File > Import > X-Plane Object (.obj) | Animations | Create the dataref animations and show/hide settings, keyed on the parts themselves |
| File > Import > X-Plane Object (.obj) | Manipulators | Set up the clickable manipulators on the meshes that have them |
| File > Import > X-Plane Object (.obj) | Lights | Create X-Plane lights as Blender lights |
| File > Import > X-Plane Object (.obj) | All LODs | Import every level of detail instead of only the first |
| File > Import > X-Plane Object (.obj) | Mark What X-Plane Hides | Draw a sphere around the show/hide parts that X-Plane would not draw with the datarefs at their default values, and leave them out of renders. They stay visible and are exported like any part |
| File > Import > X-Plane Object (.obj) | Make Export Files | Tick each imported OBJ's collection as an export file, so Export writes them again. Their texture and export settings are filled in either way, you can tick a single collection later |
| File > Import > X-Plane Object (.obj) | Show In Viewport | Switch the 3D viewport to the textured Material Preview, hide the dashed parent lines and frame everything. With many lights, Blender's own light gizmos are hidden (Overlays > Extras) and the X-Plane overlay marks the lights instead |
| File > Import > X-Plane Object (.obj) | Night Light Strength | How bright the night (LIT) texture glows. 0 shows the daytime look |
| File > Import > X-Plane Object (.obj) | Light Strength | Switches the spill lights on, such as the cockpit annunciator and panel lights. They are dataref driven in X-Plane and off in the parked pose, so 0 keeps them from lighting the scene. 1 is the brightness the light's parameters ask for |
| File > Import > X-Plane Object (.obj) | Scale | Multiplies all sizes. X-Plane uses meters, like Blender's default |

## Menus

### Add (Shift+A) > X-Plane

| Item | Kind | What it does |
|---|---|---|
| Click Zone | button | Add an invisible box that can be clicked in X-Plane, at the 3D cursor |
| Light: Library Light | button | Add at the 3D cursor: a light from X-Plane's lights.txt; color, cone and direction come from the Blender light |
| Light: Spill | button | Add at the 3D cursor: lights up the surfaces around it (cockpit flood lights, panel lights) |
| Light: Glow Sprite | button | Add at the 3D cursor: a halo drawn from part of the texture; it lights nothing |
| Wheel | button | Add an empty at the 3D cursor: where a landing gear wheel is drawn |
| Tablet Mount | button | Add an empty at the 3D cursor: where a VR tablet can be attached |
| Particle Emitter | button | Add an empty at the 3D cursor: where particles (smoke, sparks) come from |

### Animate As

| Item | Kind | What it does |
|---|---|---|
| Push Button | button | Animate the selected objects as push buttons that move in while their command is held (CMND= dataref) |
| Switch | button | Animate the selected objects as switches with a number of positions, each a dataref value |
| Knob / Lever | button | Animate the selected objects as knobs, levers or sliders that follow a dataref over a range |

### Kind Of Control

| Item | Kind | What it does |
|---|---|---|
| Button | button | Runs a command while it is held down |
| Switch, up / down | button | One command; X-Plane works out the direction from the animation |
| Switch, left / right | button | One command; X-Plane works out the direction from the animation |
| Knob | button | One command; X-Plane works out the direction from the animation |
| Switch, up / down, two commands | button | Clicking the top half runs one command, the bottom half the other |
| Switch, left / right, two commands | button | Clicking the right half runs one command, the left half the other |
| Knob, two commands | button | Clicking the right half or wheeling up runs one command, the left half the other |
| Drag runs commands | button | Dragging along a direction runs one command, dragging back the other |
| Toggle | button | Each click flips a dataref between two values |
| Push | button | Sets a dataref while held down, another value when released |
| Radio button | button | Sets a dataref to one value when clicked |
| Step | button | Adds to a dataref on click and while held, between a lowest and highest value |
| Step and wrap around | button | Like Step, but goes back to the start after the highest value |
| Knob | button | Clicking the right or left half steps a dataref up or down |
| Switch, up / down | button | Clicking the top or bottom half steps a dataref up or down |
| Switch, left / right | button | Clicking the right or left half steps a dataref up or down |
| Turn by dragging | button | Dragging turns it the way it is animated; the dataref comes from the animation |
| Turn by dragging, with detents | button | Like Turn by dragging, with ranges it stops in |
| Slide by dragging | button | Dragging along a direction moves a dataref between two values |
| Slide by dragging, with detents | button | Like Slide by dragging, with ranges it stops in (levers with gates) |
| Drag in two directions | button | Dragging left/right and up/down sets two datarefs (yokes, sticks) |
| Drag the mouse sideways | button | Dragging the mouse left and right changes a dataref, however the object is turned |
| Blocks clicks | button | Does nothing, and stops clicks reaching what is behind it |

### Kind Of Light

| Item | Kind | What it does |
|---|---|---|
| Library Light | button | A light from X-Plane's lights.txt; color, cone and direction come from the Blender light |
| Spill | button | Lights up the surfaces around it (cockpit flood lights, panel lights) |
| Glow Sprite | button | A halo drawn from part of the texture; it lights nothing |
| Library Light, By Name | button | A lights.txt light with no parameters |
| Library Light, Manual | button | A lights.txt light with its parameters set by hand |
| Not Exported | button | Only for the Blender scene |

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
| Export | button | Export the ticked files next to the .blend file, or below it at their Saved As paths |
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
