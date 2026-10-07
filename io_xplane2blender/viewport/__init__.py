"""
The X-Plane parts of the 3D View: overlays (click zones, motion, lights, unfinished work), the lever handle,
the pie menu, the X-Plane tool, the X-Plane workspace and the detail texture preview.
"""

import traceback

import bpy

from . import lever, overlay, overlay_more, settings
from .settings import view_settings

_handlers = []
_reported = set()


def _safely(draw, context) -> None:
    """A drawing problem is printed once and never stops the viewport from drawing"""
    try:
        draw(context)
    except Exception:  # noqa: BLE001
        if draw.__name__ not in _reported:
            _reported.add(draw.__name__)
            traceback.print_exc()


def _post_view():
    context = bpy.context
    s = view_settings(context)
    if s is None:
        return
    if s.show_click_zones:
        _safely(overlay.draw_zones, context)
    if s.show_motion:
        _safely(overlay_more.draw_motion, context)
    if s.show_unfinished:
        _safely(overlay_more.draw_unfinished, context)


def _post_pixel():
    context = bpy.context
    s = view_settings(context)
    if s is None or context.region is None or context.region_data is None:
        return
    if s.click_labels != "OFF":
        _safely(lambda c: overlay.draw_labels(c, s.click_labels), context)
    if s.show_motion or s.show_lever:
        _safely(overlay_more.draw_motion_labels, context)
    if s.show_lights:
        _safely(overlay_more.draw_lights, context)
    if s.show_unfinished:
        _safely(overlay_more.draw_unfinished_labels, context)


classes = (*lever.classes,)


def register():
    settings.register()
    for cls in classes:
        bpy.utils.register_class(cls)
    _handlers.append(bpy.types.SpaceView3D.draw_handler_add(_post_view, (), "WINDOW", "POST_VIEW"))
    _handlers.append(bpy.types.SpaceView3D.draw_handler_add(_post_pixel, (), "WINDOW", "POST_PIXEL"))
    bpy.types.VIEW3D_PT_overlay.append(overlay.overlay_popover)


def unregister():
    bpy.types.VIEW3D_PT_overlay.remove(overlay.overlay_popover)
    for handler in _handlers:
        bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
    _handlers.clear()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    settings.unregister()
