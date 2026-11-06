from __future__ import annotations

from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import bmesh
    import bpy

    merge_distance = float(args.get("merge_distance") or 0.0001)
    obj = bpy.context.active_object
    if obj is None or obj.type != "MESH":
        selected = [o for o in bpy.context.selected_objects if o.type == "MESH"]
        if not selected:
            raise RuntimeError("Select a mesh object")
        obj = selected[0]

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    prev_mode = obj.mode
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        mesh = obj.data
        editable = bmesh.from_edit_mesh(mesh)
        before = len(editable.verts)
        bmesh.ops.remove_doubles(
            editable,
            verts=list(editable.verts),
            dist=merge_distance,
        )
        bmesh.update_edit_mesh(mesh)
        merged = before - len(editable.verts)
    finally:
        bpy.ops.object.mode_set(mode=prev_mode if prev_mode in {"OBJECT", "EDIT"} else "OBJECT")
    return f"cleaned {obj.name} merged={merged} merge_distance={merge_distance}"


RUNNER = ToolRunner(name="clean_mesh", permission="confirm", run=run)
