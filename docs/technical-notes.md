# Technical Notes

How the add-on turns Blender into X-Plane and back, for when the guides are not enough.

## Lights

- The light's rotation is its direction for every kind of light. Spot Size is the cone and Color the color: library
  lights and spills are always written from them, and for **Library Light, Manual** the typed `WIDTH` and `R G B`
  follow them.
- Power (watts, while it is above 0) is the intensity in candela, at 4π²/683 watts per candela. Custom Distance (once
  switched on) is the reach in meters, which only spills have: a Spill's **Reach (m)**, or the size of a library spill.
  A light lit by its intensity has no reach in X-Plane, so its Custom Distance is left alone.
- A light is never changed by being looked at: only a change made while the add-on is watching is passed on, so
  opening a file or selecting a light changes nothing. What the preview multiplied the power by is remembered and
  taken out again.
- **Preview As In X-Plane** only changes settings the exporter never reads: the power (except for glow sprites, whose
  power is the exported alpha), the cutoff distance and ray visibility.
- lights.txt gives a light a billboard (the visible halo, which lights nothing) and / or a spill. On import, spills
  become point or spot lights with the cone and direction of the light's parameters (`WIDTH` is the cosine of half the
  cone angle, `DX DY DZ` the direction) and the power from its candela or radius. The power the light has when on is
  stored on the light as `xplane_watts_when_on`.
- `LIGHT_CUSTOM` is the exception: the exporter writes the Blender power as the light's alpha, and colors outside 0 to
  1 (some halos use -1 as a placeholder) are typed in (**Color > Typed**).
- A `LIGHT_SPILL_CUSTOM`'s alpha is the Spill's **Dim** and its direction is written normalized.
- Blender draws every light with a line to the ground and, for a spot, a circle whose size depends only on the spot's
  angle (10 m times the sine of half the angle), so hundreds of lights bury an aircraft. Only hiding them helps:
  **Overlays > Extras** off hides them and keeps the lights lighting the scene, while hiding the lights themselves
  would switch their light off too.

## Animation Presets

- Movement is along or around the object's own axis, from where it stands. Keys are linear, as X-Plane interpolates
  them, and turns of more than 90° get keys in between so whole turns are kept.
- **Replace** starts again from where the object stood before the preset first animated it.
- The **Button** preset reproduces hand-made button animations key for key.

## Importing

- A part pushed in and turned by the same dataref is one object, and so is a part turned about up to three axes by one
  dataref. A show / hide that holds a single part is on the part. Where several parts share an animation the biggest
  one carries it and the others hang on it. An Empty is only made where needed: the outer animations of a part under
  animations of different datarefs, or a static turn that a panel's parts share (a ` frame` Empty). Animations with
  nothing in them are left out and counted in the import report.
- The parked pose is one frame for every part, and the scene opens on it. No key is before frame 1, where the playhead
  cannot go.
- Header lines the add-on has no setting for are kept as extra OBJ lines with the line that ends them (such as
  `ATTR_cull` after `ATTR_no_cull`). This includes `ATTR_albedo_opacity <min> <max> <dataref>`, which X-Plane 12 reads
  although the OBJ8 specification does not list it (it fades the day texture by a dataref, for example ice building
  up), kept with its `ATTR_albedo_opacity_reset`.
- Textures are named as the OBJ names them: X-Plane loads `wing.dds` for `TEXTURE wing.png`, so Blender shows the .dds
  and the export still names the .png, and a texture that is not shipped stays named. With a livery the livery's
  textures are shown and the OBJ still names the aircraft's own.
- `ATTR_landing_gear` becomes a **Wheel** in its animation, and magnets and emitters keep their turn inside turned
  frames.
- Older files that put an animation line after geometry in a block are read the way X-Plane reads them: the line only
  moves what follows it.
- Triangles with no area are left out: they draw nothing, and Blender's normals around them change when a part is
  turned. Normals are kept exactly when the importer or the exporter turns a part.
- Drag click zones are kept free of children and in the frame their animation turns in, which the exporter needs. A
  drag rotate with a lift becomes **Turn by dragging, with detents** with **Detent Dataref > Own Range** on (Laminar's
  levers lift a dataref from 0 to 1); one with detent lines but no lift stays **Turn by dragging** and keeps them. A
  drag axis with `ATTR_axis_detented` becomes **Slide by dragging, with detents**.
- Empties are drawn at a quarter of the largest part hanging on them (a few millimeters for a knob, at most 6 cm) and a
  spot light's cone only as long as its reach (15 cm for a light that is off). The dashed parent lines are turned off.
- Re-exporting complex drag rotate manipulators needs the parent and child animation layout XPlane2Blender asks for.

## Exporting

- The exporter reads an object's first material only.
- Hidden objects are never exported.
- With **Smaller Files (share vertices)** each vertex is written once per file, and normals that differ only by
  Blender's rounding (about 1e-5) are merged.
