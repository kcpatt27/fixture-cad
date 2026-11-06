from __future__ import annotations

from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import bpy

    sel = bpy.context.selected_objects
    if not sel:
        return "Nothing selected."
    lines = []
    for obj in sel:
        lines.append(f"{obj.name}: type={obj.type}")
        if obj.type == "MESH" and obj.data:
            lines.append(
                f"  verts={len(obj.data.vertices)} polys={len(obj.data.polygons)}"
            )
    focus = args.get("focus")
    if focus:
        lines.append(f"focus={focus}")
    return "\n".join(lines)


RUNNER = ToolRunner(name="explain_selection", permission="auto", run=run)
