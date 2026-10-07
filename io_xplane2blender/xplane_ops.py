"""
Operators and helpers for dataref keyframes, exporting next to the .blend file, and messages.
"""

from typing import Optional

import bpy

from io_xplane2blender.xplane_helpers import get_action_fcurves, remove_action_fcurve


# Function: findFCurveByPath
# Helper function to find an FCurve by an data-path.
#
# Parameters:
#   list - FCurves
#   string - data path.
#
# Returns:
#   FCurve or None if no FCurve could be found.
def findFCurveByPath(fcurves, path):
    i = 0
    fcurve = None

    # find fcurve
    while i < len(fcurves):
        if fcurves[i].data_path == path:
            fcurve = fcurves[i]
            i = len(fcurves)
        i += 1
    return fcurve


# Function: makeKeyframesLinear
# Sets interpolation mode of keyframes to linear.
#
# Parameters:
#   obj - Blender object
#   string path - data path.
#
# Todos:
#   - not working
def makeKeyframesLinear(obj, path):
    fcurve = findFCurveByPath(get_action_fcurves(obj), path)

    if fcurve:
        for keyframe in fcurve.keyframe_points:
            keyframe.interpolation = "LINEAR"


# Function: getDatarefValuePath
# Returns the data path for a <XPlaneDataref> value.
#
# Parameters:
#   int index - Index of the <XPlaneDataref>
#
# Returns:
#   string - data path
def getDatarefValuePath(index: int, bone: Optional[bpy.types.Bone] = None) -> str:
    """
    Returns the keyframe data path for an XPlaneDataref value on a bone or object"

    index is tied with the remove_xplane_dataref operator.
    """

    if bone:
        return 'bones["%s"].xplane.datarefs[%d].value' % (bone.name, index)
    else:
        return "xplane.datarefs[" + str(index) + "].value"


def removeDatarefFCurve(
    id_data: bpy.types.ID, index: int, bone: Optional[bpy.types.Bone] = None
) -> None:
    """
    Removes the FCurve of the removed XPlaneDataref at index, and moves the FCurves
    of the datarefs after it down one index so they stay with their datarefs
    """
    fcurves = {f.data_path: f for f in get_action_fcurves(id_data)}

    removed = fcurves.get(getDatarefValuePath(index, bone))
    if removed:
        remove_action_fcurve(id_data, removed)

    later_indices = sorted(
        i
        for i in range(index + 1, len(fcurves) + index + 1)
        if getDatarefValuePath(i, bone) in fcurves
    )
    for i in later_indices:
        fcurves[getDatarefValuePath(i, bone)].data_path = getDatarefValuePath(
            i - 1, bone
        )


# Class: OBJECT_OT_add_xplane_dataref_keyframe
# Adds a Keyframe to the value of a <XPlaneDataref> of an object.
class OBJECT_OT_add_xplane_dataref_keyframe(bpy.types.Operator):
    bl_label = "Add Dataref keyframe"
    bl_idname = "object.add_xplane_dataref_keyframe"
    bl_description = "Add/Update an X-Plane Dataref keyframe"

    # index here refers to the index of the datarefs collection,
    # NOT the keyframe index
    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.object
        path = getDatarefValuePath(self.index)
        obj.xplane.datarefs[self.index].keyframe_insert(
            data_path="value", group="XPlane Datarefs"
        )
        makeKeyframesLinear(obj, path)

        return {"FINISHED"}


# Class: OBJECT_OT_remove_xplane_dataref_keyframe
# Removes a Keyframe from the value of a <XPlaneDataref> of an object.
class OBJECT_OT_remove_xplane_dataref_keyframe(bpy.types.Operator):
    bl_label = "Remove Dataref keyframe"
    bl_idname = "object.remove_xplane_dataref_keyframe"
    bl_description = "Remove the X-Plane Dataref keyframe"

    # index here refers to the index of the datarefs collection,
    # NOT the keyframe index
    index: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.object
        path = getDatarefValuePath(self.index)
        obj.xplane.datarefs[self.index].keyframe_delete(
            data_path="value", group="XPlane Datarefs"
        )

        return {"FINISHED"}


# Class: BONE_OT_add_xplane_dataref_keyframe
# Adds a Keyframe to the value of a <XPlaneDataref> of a bone.
class BONE_OT_add_xplane_dataref_keyframe(bpy.types.Operator):
    bl_label = "Add Dataref keyframe"
    bl_idname = "bone.add_xplane_dataref_keyframe"
    bl_description = "Add/Update an X-Plane Dataref keyframe"

    # index here refers to the index of the datarefs collection,
    # NOT the keyframe index
    index: bpy.props.IntProperty()

    # bpy.data.objects["Armature"].data.keyframe_insert(data_path='bones["Bone"].my_prop_group.nested', group="Nested Property")
    def execute(self, context):
        bone = (
            context.active_bone
        )  # context.bone is not always available, for instance, during test_creation_helpers
        # Other uses will be replaced as needed. context.object doesn't appear to be affected
        # See also: https://blender.stackexchange.com/q/31759
        armature = context.object
        path = getDatarefValuePath(self.index, bone)

        armature.data.keyframe_insert(
            data_path=path, group="XPlane Datarefs " + bone.name
        )

        return {"FINISHED"}


# Class: BONE_OT_remove_xplane_dataref_keyframe
# Removes a Keyframe from the value of a <XPlaneDataref> of a bone.
class BONE_OT_remove_xplane_dataref_keyframe(bpy.types.Operator):
    bl_label = "Remove Dataref keyframe"
    bl_idname = "bone.remove_xplane_dataref_keyframe"
    bl_description = "Remove the X-Plane Dataref keyframe"

    # index here refers to the index of the datarefs collection,
    # NOT the keyframe index
    index: bpy.props.IntProperty()

    def execute(self, context):
        bone = context.bone
        path = getDatarefValuePath(self.index)
        armature = context.object
        path = getDatarefValuePath(self.index, bone)
        armature.data.keyframe_delete(
            data_path=path, group="XPlane Datarefs " + bone.name
        )

        return {"FINISHED"}


# Class: SCENE_OT_export_to_relative_dir
# Exports OBJS into the same folder as the .blend file, and/or folders beneath it
class SCENE_OT_export_to_relative_dir(bpy.types.Operator):
    bl_label = "Export OBJs"
    bl_idname = "scene.export_to_relative_dir"
    bl_description = "Exports OBJs relative to the .blend file"

    # initial_dir that will be prepended to the path.
    initial_dir: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.export.xplane_obj(filepath=self.initial_dir, export_is_relative=True)
        return {"FINISHED"}


class XPLANE_OT_XPlaneMessage(bpy.types.Operator):
    bl_idname = "xplane.msg"
    bl_label = "XPlane2Blender Message"

    msg_text: bpy.props.StringProperty()
    icon: bpy.props.StringProperty(default="ERROR")
    # fmt: off
    invoke_style: bpy.props.EnumProperty(
        items=[
            ("invoke_popup",        "Invoke Popup",        "A popup without confirm button"),
            ("invoke_props_dialog", "Invoke Popup Dialog", "A popup with confirm button"),
        ],
        name="Invoke Style",
        description="Which popup style to use",
        default="invoke_props_dialog",
    )
    # fmt: on

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return getattr(wm, self.invoke_style)(self, width=500)

    def draw(self, context):
        self.layout.row().label(text=self.msg_text, icon=self.icon)


_ops = (
    OBJECT_OT_add_xplane_dataref_keyframe,
    OBJECT_OT_remove_xplane_dataref_keyframe,
    BONE_OT_add_xplane_dataref_keyframe,
    BONE_OT_remove_xplane_dataref_keyframe,
    SCENE_OT_export_to_relative_dir,
    XPLANE_OT_XPlaneMessage,
)

register, unregister = bpy.utils.register_classes_factory(_ops)
