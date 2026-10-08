"""
The X-Plane parts of the 3D View: overlays (click zones, motion, lights, unfinished work), the lever handle,
the pie menu, the X-Plane tool, the X-Plane workspace, the detail texture preview and Tidy Up.
"""

import traceback

import bpy

from . import (
    detail_preview,
    lever,
    overlay,
    overlay_more,
    pie,
    settings,
    tidy,
    tool,
    workspace,
)
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
    if s.show_lights:
        _safely(overlay_more.draw_light_cones, context)
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


classes = (
    *lever.classes,
    *pie.classes,
    *tidy.classes,
    *tool.classes,
    *workspace.classes,
    *detail_preview.classes,
)


def register():
    settings.register()
    for cls in classes:
        bpy.utils.register_class(cls)
    _handlers.append(
        bpy.types.SpaceView3D.draw_handler_add(_post_view, (), "WINDOW", "POST_VIEW")
    )
    _handlers.append(
        bpy.types.SpaceView3D.draw_handler_add(_post_pixel, (), "WINDOW", "POST_PIXEL")
    )
    bpy.types.VIEW3D_PT_overlay.append(overlay.overlay_popover)
    bpy.types.TOPBAR_MT_workspace_menu.append(workspace.workspace_menu_entry)
    tool.register_tool()
    pie.register_keymap()


def unregister():
    pie.unregister_keymap()
    tool.unregister_tool()
    bpy.types.TOPBAR_MT_workspace_menu.remove(workspace.workspace_menu_entry)
    bpy.types.VIEW3D_PT_overlay.remove(overlay.overlay_popover)
    for handler in _handlers:
        bpy.types.SpaceView3D.draw_handler_remove(handler, "WINDOW")
    _handlers.clear()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    settings.unregister()
