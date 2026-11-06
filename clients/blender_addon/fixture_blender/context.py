from __future__ import annotations

from pathlib import Path
from typing import Any


def document_name(filepath: str | None) -> str:
    return Path(filepath).name if filepath else "untitled"


def build_context() -> dict[str, Any]:
    import bpy

    selected: list[dict[str, Any]] = []
    for obj in bpy.context.selected_objects:
        entry: dict[str, Any] = {
            "name": obj.name,
            "type": obj.type,
        }
        if obj.type == "MESH" and obj.data is not None:
            mesh = obj.data
            entry["shape"] = "Mesh"
            entry["properties"] = {
                "vertices": len(mesh.vertices),
                "polygons": len(mesh.polygons),
            }
        selected.append(entry)

    mode = getattr(bpy.context, "mode", "") or ""
    blend = document_name(bpy.data.filepath)
    return {
        "active_document": blend,
        "workbench_or_mode": mode,
        "selected_objects": selected,
        "extra": {
            "active_object": bpy.context.active_object.name
            if bpy.context.active_object
            else ""
        },
    }
