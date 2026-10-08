"""
For panels that look at every object of a scene. Blender redraws a panel whenever the mouse moves over a button, and
an aircraft has thousands of objects, so what such a panel found is kept until the scene changes (a count that goes
up on every change) or for a second, instead of being found again on every redraw.
"""

import time

import bpy
from bpy.app.handlers import persistent

CACHE_SECONDS = 1.0
_changes = [0]


@persistent
def scene_changed(*_args) -> None:
    """Whatever the scene changes, what was found is stale. This only counts, the work is done when drawing"""
    _changes[0] += 1


def count() -> int:
    """Goes up whenever anything in the scene changes: a setting, the selection, an object added or removed"""
    return _changes[0]


class Remembered:
    """The last result of one calculation: kept while its key is the same, for a second at most"""

    def __init__(self):
        self.key = None
        self.value = None
        self.when = 0.0
        self.version = 0

    def get(self, key, make):
        now = time.monotonic()
        if key != self.key or now - self.when > CACHE_SECONDS:
            self.key, self.value, self.when = key, make(), now
            self.version += 1
        return self.value


def register():
    bpy.app.handlers.depsgraph_update_post.append(scene_changed)


def unregister():
    if scene_changed in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(scene_changed)
