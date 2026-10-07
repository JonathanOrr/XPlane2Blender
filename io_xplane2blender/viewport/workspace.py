"""
The X-Plane workspace: a copy of Layout set up for building a cockpit. Its 3D View outlines click zones, labels
the selected ones, shows motion, lights and unfinished work and has the lever handle, with textures in Solid shading;
the Properties editor opens on the Object tab. Made the first time it is opened and saved with the .blend like any
workspace. Opened from the workspace tabs' right-click menu, the Scene tab's X-Plane Tools and the pie menu.
"""

import bpy

NAME = "X-Plane"


def set_up(workspace: bpy.types.WorkSpace) -> None:
    """Turns a workspace into the X-Plane workspace (its name is left alone)"""
    workspace.object_mode = "OBJECT"
    for screen in workspace.screens:
        view = screen.xplane_view
        view.show_click_zones = True
        view.click_labels = "SELECTED"
        view.show_motion = True
        view.show_lever = True
        view.show_lights = True
        view.show_unfinished = True
        for area in screen.areas:
            for space in area.spaces:
                if space.type == "VIEW_3D" and space.shading.type == "SOLID":
                    space.shading.color_type = "TEXTURE"
                elif space.type == "PROPERTIES":
                    try:
                        space.context = "OBJECT"
                    except TypeError:  # Not offered while nothing is active
                        pass


class XPLANE_OT_workspace(bpy.types.Operator):
    """Open the X-Plane workspace: the 3D View with the X-Plane overlays and lever handle, Properties on the Object
    tab. It is made from Layout the first time"""

    bl_idname = "xplane.workspace"
    bl_label = "X-Plane Workspace"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.window is not None

    def execute(self, context):
        workspace = bpy.data.workspaces.get(NAME)
        if workspace is None:
            base = bpy.data.workspaces.get("Layout") or context.workspace
            before = set(bpy.data.workspaces)
            with context.temp_override(workspace=base):
                bpy.ops.workspace.duplicate()
            made = [w for w in bpy.data.workspaces if w not in before]
            if not made:
                self.report({"WARNING"}, "The workspace could not be made")
                return {"CANCELLED"}
            workspace = made[0]
            workspace.name = NAME
            set_up(workspace)
        context.window.workspace = workspace
        return {"FINISHED"}


def workspace_menu_entry(self, context):
    self.layout.separator()
    self.layout.operator(XPLANE_OT_workspace.bl_idname, icon="AUTO")


classes = (XPLANE_OT_workspace,)
