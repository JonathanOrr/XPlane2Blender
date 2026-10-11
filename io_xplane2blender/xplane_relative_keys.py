"""
Relative keys: a part's movement keyed on its delta location (Object > Transform > Delta Transform) instead of its
location. The location is then only where the part stands, so it can be moved anywhere afterwards and its animation
goes with it. Make Keys Relative turns location keys into delta location keys; the exported OBJ stays the same.
"""

from typing import Dict, List, Optional, Sequence, Tuple

import bpy

from .xplane_helpers import get_action_fcurves

LOCATION, DELTA_LOCATION = "location", "delta_location"
# Where the presets and the importer show the parked pose, and so where a part stands
REST_FRAME = 1.0


def keyed_paths(obj: bpy.types.Object) -> set:
    return {fc.data_path for fc in get_action_fcurves(obj)}


def moves_by_delta(obj: bpy.types.Object) -> bool:
    """Whether the object's movement is keyed on its delta transform"""
    return any(path.startswith("delta_") for path in keyed_paths(obj))


def _location_curves(obj: bpy.types.Object) -> List[bpy.types.FCurve]:
    return [fc for fc in get_action_fcurves(obj) if fc.data_path == LOCATION]


def _sharers(objects: Sequence[bpy.types.Object]) -> Dict[int, List[bpy.types.Object]]:
    """The objects animated by each location FCurve: an Action can be shared, and all of them change together"""
    found: Dict[int, List[bpy.types.Object]] = {}
    for obj in objects:
        if obj.animation_data and obj.animation_data.action:
            for fc in _location_curves(obj)[:1]:
                found.setdefault(fc.as_pointer(), []).append(obj)
    return found


def _make_relative(obj: bpy.types.Object, sharers: List[bpy.types.Object]) -> Optional[str]:
    curves = _location_curves(obj)
    if not curves:
        return "no location keys"
    if any(DELTA_LOCATION in keyed_paths(o) for o in sharers):
        return "delta location keyed already"
    rest = {fc.array_index: fc.evaluate(REST_FRAME) for fc in curves}
    # A delta location kept still is added to the keys, so it must be the same on every object sharing them
    if any(o.delta_location[i] != obj.delta_location[i] for o in sharers for i in rest):
        return "keys shared with parts placed differently"
    for fc in curves:
        shift = obj.delta_location[fc.array_index] - rest[fc.array_index]
        fc.data_path = DELTA_LOCATION
        for key in fc.keyframe_points:
            key.co[1] += shift
            key.handle_left[1] += shift
            key.handle_right[1] += shift
        fc.update()
    for o in sharers:
        for i, value in rest.items():
            o.location[i] = value
    return None


def make_relative(objects: Sequence[bpy.types.Object]) -> Tuple[int, List[Tuple[str, str]]]:
    """
    Turns the location keys of the objects into delta location keys, each standing where it is at frame 1.
    Returns how many were done, and (name, why) for each object left alone
    """
    sharers = _sharers(bpy.data.objects)
    done, skipped, made = 0, [], set()
    for obj in objects:
        if obj.name in made:
            done += 1  # It shares its keys with an object done before
            continue
        curves = _location_curves(obj)
        group = sharers.get(curves[0].as_pointer(), [obj]) if curves else [obj]
        reason = _make_relative(obj, group)
        if reason:
            skipped.append((obj.name, reason))
        else:
            done += 1
            made.update(o.name for o in group)
    return done, skipped


def make_relative_one(obj: bpy.types.Object) -> Optional[str]:
    """make_relative for an object whose keys are its own, as the importer makes them"""
    return _make_relative(obj, [obj])


class XPLANE_OT_make_keys_relative(bpy.types.Operator):
    """Key the movement of the selected (and active) objects on their delta location instead of their location, so that they can
    be moved anywhere and their animation goes with them. The exported OBJ stays the same"""

    bl_idname = "xplane.make_keys_relative"
    bl_label = "Make Keys Relative"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and (context.object is not None or bool(context.selected_objects))

    def execute(self, context):
        objects = list(context.selected_objects)
        if context.object is not None and context.object not in objects:
            objects.append(context.object)
        done, skipped = make_relative(objects)
        context.scene.frame_set(context.scene.frame_current)
        reasons: Dict[str, int] = {}
        for _, reason in skipped:
            reasons[reason] = reasons.get(reason, 0) + 1
        text = f"Made the keys of {done} object(s) relative"
        text += "".join(f"; {n} left alone, {reason}" for reason, n in reasons.items())
        self.report({"INFO"} if done else {"WARNING"}, text)
        return {"FINISHED"} if done else {"CANCELLED"}
