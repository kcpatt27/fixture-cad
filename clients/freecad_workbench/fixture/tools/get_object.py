from __future__ import annotations

from typing import Any

from .base import ToolRunner

MAX_RESULT_CHARS = 2400


def _placement_xyz(obj: Any) -> str | None:
    try:
        placement = getattr(obj, "Placement", None)
        if placement is None:
            return None
        base = placement.Base
        return f"({float(base.x):.3f}, {float(base.y):.3f}, {float(base.z):.3f})"
    except Exception:  # noqa: BLE001
        return None


def _shape_facts(obj: Any) -> list[str]:
    lines: list[str] = []
    shape = getattr(obj, "Shape", None)
    if shape is None:
        return lines
    try:
        if hasattr(shape, "isNull") and shape.isNull():
            return lines
        volume = float(shape.Volume)
        lines.append(f"volume={volume:.3f}")
        bbox = shape.BoundBox
        lines.append(
            f"bbox=({float(bbox.XLength):.3f}, {float(bbox.YLength):.3f}, "
            f"{float(bbox.ZLength):.3f})"
        )
        shape_type = getattr(shape, "ShapeType", None)
        if shape_type:
            lines.append(f"shape={shape_type}")
    except Exception:  # noqa: BLE001
        pass
    return lines


def _body_children(obj: Any) -> list[str]:
    lines: list[str] = []
    type_id = str(getattr(obj, "TypeId", ""))
    if "PartDesign::Body" not in type_id:
        return lines
    try:
        group = list(getattr(obj, "Group", []) or [])
    except Exception:  # noqa: BLE001
        return lines
    if not group:
        lines.append("children=(none)")
        return lines
    parts = []
    for child in group:
        parts.append(
            f"{getattr(child, 'Name', '?')}({getattr(child, 'TypeId', type(child).__name__)})"
        )
    lines.append("children=" + ", ".join(parts))
    tip = getattr(obj, "Tip", None)
    if tip is not None:
        lines.append(f"tip={getattr(tip, 'Name', tip)}")
    return lines


def _feature_props(obj: Any) -> list[str]:
    lines: list[str] = []
    type_id = str(getattr(obj, "TypeId", ""))
    if "Pad" in type_id or "Pocket" in type_id:
        length = getattr(obj, "Length", None)
        if length is not None:
            try:
                lines.append(f"Length={float(length)}")
            except Exception:  # noqa: BLE001
                lines.append(f"Length={length}")
        reversed_flag = getattr(obj, "Reversed", None)
        if reversed_flag is not None:
            lines.append(f"Reversed={bool(reversed_flag)}")
    if "Sketch" in type_id:
        count = getattr(obj, "GeometryCount", None)
        if count is not None:
            lines.append(f"GeometryCount={int(count)}")
    return lines


def collect_object_facts(object_name: str) -> dict[str, Any]:
    """Structured facts for one FreeCAD object (empty dict if missing)."""
    import FreeCAD

    doc = FreeCAD.ActiveDocument
    if doc is None:
        return {"error": "No active document."}
    name = str(object_name).strip()
    obj = doc.getObject(name)
    if obj is None:
        return {"error": f"Object not found: {name}"}
    facts: dict[str, Any] = {
        "name": str(obj.Name),
        "type": str(getattr(obj, "TypeId", type(obj).__name__)),
        "label": str(getattr(obj, "Label", obj.Name)),
    }
    xyz = _placement_xyz(obj)
    if xyz:
        facts["placement"] = xyz
    shape_lines = _shape_facts(obj)
    if shape_lines:
        facts["shape"] = shape_lines
    children = _body_children(obj)
    if children:
        facts["body"] = children
    props = _feature_props(obj)
    if props:
        facts["properties"] = props
    return facts


def format_object_facts(facts: dict[str, Any]) -> str:
    if "error" in facts:
        return str(facts["error"])
    lines = [
        f"{facts.get('name')} | {facts.get('type')} | {facts.get('label')}",
    ]
    if facts.get("placement"):
        lines.append(f"placement={facts['placement']}")
    for key in ("shape", "body", "properties"):
        vals = facts.get(key)
        if isinstance(vals, list):
            lines.extend(f"  {v}" for v in vals)
    text = "\n".join(lines)
    if len(text) > MAX_RESULT_CHARS:
        return text[: MAX_RESULT_CHARS - 1] + "…"
    return text


def run(args: dict[str, Any]) -> str:
    name = str(args.get("object_name") or "").strip()
    if not name:
        raise ValueError("object_name is required")
    return format_object_facts(collect_object_facts(name))


RUNNER = ToolRunner(name="get_object", permission="auto", run=run)
