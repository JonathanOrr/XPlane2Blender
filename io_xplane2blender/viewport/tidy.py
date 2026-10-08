"""
Tidy Up: draws empties and light cones as small as what hangs on them, in a scene that is already imported or built.
A crowded cockpit can then be read and clicked. The importer does the same while it imports.
"""

import bpy

from io_xplane2blender import xplane_display_sizes as sizes


class XPLANE_OT_tidy_viewport(bpy.types.Operator):
    """Draw empties and spot light cones as small as the parts hanging on them, so a crowded cockpit can be read and clicked. Only the viewport changes, nothing is exported differently"""

    bl_idname = "xplane.tidy_viewport"
    bl_label = "Tidy Empties And Light Cones"
    bl_options = {"REGISTER", "UNDO"}

    selected_only: bpy.props.BoolProperty(
        name="Selected Only",
        description="Only the selected empties and lights, otherwise all of them",
        default=False,
    )

    @classmethod
    def poll(cls, context):
        return context.scene is not None

    def execute(self, context):
        everything = context.scene.objects
        targets = context.selected_objects if self.selected_only else everything
        part_sizes = sizes.part_sizes(o for o in everything if o.type == "MESH")
        empties = sizes.fit_empty_sizes(targets, part_sizes)
        cones = sizes.tidy_lights(targets)
        self.report(
            {"INFO"}, f"{empties} empty(ies) resized, {cones} light cone(s) shortened"
        )
        return {"FINISHED"}


classes = (XPLANE_OT_tidy_viewport,)
