"""
Keeps the numbers an X-Plane light shares with its Blender light equal (see links.py), in both directions:

- A number changed on the X-Plane side (a setting of the card, the typed parameters) is pushed to the Blender light,
  right away, by the settings' update functions.
- A number changed on the Blender side (Power, Custom Distance, Spot Size, Color) is pulled into the X-Plane light by a
  handler that looks at the selected lights after every change. It only acts on a change it saw happen: a light's
  numbers are written down the first time it is looked at, so opening a file or selecting a light never changes it.
"""

from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

import bpy
from bpy.app.handlers import persistent

from io_xplane2blender import xplane_constants as C

from . import links
from .links import LINKS, STRENGTH, Link, links_of  # noqa: F401

# More selected lights than this are left to the next change, so that selecting everything stays quick
MAX_LIGHTS = 64
_paused = [0]
# By light: what each linked number of the Blender side was the last time it was looked at
_seen: Dict[str, Dict[str, Any]] = {}


@contextmanager
def paused() -> Iterator[None]:
    """Nothing is pushed or pulled inside: for code that sets both sides itself, such as the importer"""
    _paused[0] += 1
    try:
        yield
    finally:
        _paused[0] -= 1


def is_paused() -> bool:
    return _paused[0] > 0


def remember(data: bpy.types.Light) -> None:
    """Writes down the Blender side of every linked number as it is now, so that it is not taken for a change"""
    _seen[data.name_full] = {
        link.quantity: link.blender(data) for link in links_of(data)
    }


def push(data: bpy.types.Light, quantity: Optional[str] = None) -> None:
    """Makes the Blender light say what the X-Plane light has (one number, or all of them)"""
    with paused():
        for link in links_of(data):
            if quantity in (None, link.quantity):
                link.set_blender(data)
    remember(data)


def adopt_blender(
    data: bpy.types.Light, obj: Optional[bpy.types.Object] = None
) -> None:
    """
    Makes the X-Plane light say what the Blender light has, for every number that is set there: a new typed light takes
    the color and cone of the light it is made from, instead of starting from default values. With the object, it also
    takes the direction the light shines, so that a cone does not start with none
    """
    if data.xplane.type != C.LIGHT_NON_EXPORTING:
        with paused():
            for link in LINKS:
                if link.adoptable(data) and link.is_set(data):
                    link.set_stored(data, link.from_blender(data))
            if obj is not None:
                links.adopt_direction(data, obj)
    remember(data)


def stored_changed(data: bpy.types.Light, quantity: Optional[str] = None) -> None:
    """The X-Plane side of a number was changed (None: any of them), the Blender side follows"""
    if not is_paused():
        push(data, quantity)


def pull(data: bpy.types.Light) -> None:
    """Takes what was changed on the Blender side of the light into the X-Plane side"""
    before = _seen.get(data.name_full)
    if before is None:
        remember(data)
        return
    with paused():
        now = {}
        for link in links_of(data):
            current = link.blender(data)
            now[link.quantity] = current
            if link.quantity not in before:
                continue
            reaction = link.reaction(data, before[link.quantity], current)
            if reaction == "pull":
                link.set_stored(data, link.from_blender(data))
            elif reaction == "push":
                link.set_blender(data)
                now[link.quantity] = link.blender(data)
        _seen[data.name_full] = now


def _lights_in_use(context) -> Dict[str, bpy.types.Light]:
    found = {}
    try:
        objects = list(context.selected_objects)
        if context.object is not None:
            objects.append(context.object)
    except (
        AttributeError,
        RuntimeError,
    ):  # No view layer yet, such as while a file is loading
        return found
    for obj in objects:
        if obj.type == "LIGHT":
            found[obj.data.name_full] = obj.data
    return found


@persistent
def blender_changed(*_args) -> None:
    """After every change: the selected lights take in what was changed on their Blender side"""
    if is_paused() or getattr(bpy.context.screen, "is_animation_playing", False):
        return
    for data in list(_lights_in_use(bpy.context).values())[:MAX_LIGHTS]:
        pull(data)


@persistent
def forget(*_args) -> None:
    _seen.clear()


def register() -> None:
    bpy.app.handlers.depsgraph_update_post.append(blender_changed)
    bpy.app.handlers.load_post.append(forget)


def unregister() -> None:
    for handlers, function in (
        (bpy.app.handlers.depsgraph_update_post, blender_changed),
        (bpy.app.handlers.load_post, forget),
    ):
        if function in handlers:
            handlers.remove(function)
    _seen.clear()
