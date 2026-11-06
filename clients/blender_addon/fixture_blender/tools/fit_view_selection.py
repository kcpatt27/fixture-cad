from __future__ import annotations

from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import bpy

    _ = args
    for window in bpy.context.window_manager.windows:
        screen = window.screen
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for region in area.regions:
                if region.type != "WINDOW":
                    continue
                with bpy.context.temp_override(window=window, area=area, region=region):
                    bpy.ops.view3d.view_selected()
                return "view fitted"
    raise RuntimeError("No VIEW_3D area for view_selected")


RUNNER = ToolRunner(name="fit_view_selection", permission="auto", run=run)
