from __future__ import annotations

from typing import Any

from .base import ToolRunner

DEFAULT_MAX_OBJECTS = 40
MAX_OBJECTS_CAP = 40
MAX_RESULT_CHARS = 2400


def _parent_name(obj: Any) -> str | None:
    try:
        parent = getattr(obj, "getParentGeoFeatureGroup", None)
        if callable(parent):
            group = parent()
            if group is not None:
                return str(group.Name)
    except Exception:  # noqa: BLE001
        pass
    try:
        in_list = getattr(obj, "InList", None) or []
        for candidate in in_list:
            type_id = getattr(candidate, "TypeId", "")
            if "Body" in str(type_id) or "Part" in str(type_id):
                return str(candidate.Name)
    except Exception:  # noqa: BLE001
        pass
    return None


def collect_document_objects(*, max_objects: int = DEFAULT_MAX_OBJECTS) -> list[dict[str, str]]:
    """Return capped object facts from the active FreeCAD document."""
    import FreeCAD

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return []
    cap = max(1, min(int(max_objects), MAX_OBJECTS_CAP))
    rows: list[dict[str, str]] = []
    for obj in list(doc.Objects)[:cap]:
        row: dict[str, str] = {
            "name": str(obj.Name),
            "type": str(getattr(obj, "TypeId", type(obj).__name__)),
            "label": str(getattr(obj, "Label", obj.Name)),
        }
        parent = _parent_name(obj)
        if parent:
            row["parent"] = parent
        rows.append(row)
    return rows


def format_object_list(rows: list[dict[str, str]], *, truncated: bool = False) -> str:
    if not rows:
        return "No active document objects."
    lines = [f"{r['name']} | {r['type']} | {r['label']}" + (f" | parent={r['parent']}" if r.get("parent") else "") for r in rows]
    text = "\n".join(lines)
    if truncated:
        text = text + f"\n… truncated at {len(rows)} objects"
    if len(text) > MAX_RESULT_CHARS:
        return text[: MAX_RESULT_CHARS - 1] + "…"
    return text


def run(args: dict[str, Any]) -> str:
    raw_max = args.get("max_objects", DEFAULT_MAX_OBJECTS)
    try:
        max_objects = int(raw_max)
    except (TypeError, ValueError):
        max_objects = DEFAULT_MAX_OBJECTS
    max_objects = max(1, min(max_objects, MAX_OBJECTS_CAP))

    import FreeCAD

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return "No active document."
    total = len(list(doc.Objects))
    rows = collect_document_objects(max_objects=max_objects)
    return format_object_list(rows, truncated=total > len(rows))


RUNNER = ToolRunner(name="list_document_objects", permission="auto", run=run)
