from __future__ import annotations

from typing import Any

from ._partdesign import active_document, ensure_name_available, resolve_named, transaction
from .base import ToolRunner

_PLANE_ROLES = {
    "XY": "XY_Plane",
    "XZ": "XZ_Plane",
    "YZ": "YZ_Plane",
}


def run(args: dict[str, Any]) -> str:
    doc = active_document()
    body_name = str(args["body_name"]).strip()
    plane = str(args["plane"]).upper()
    name = str(args.get("name") or "Sketch").strip()
    if plane not in _PLANE_ROLES:
        raise ValueError(f"Unsupported sketch plane: {plane}")
    if not name:
        raise ValueError("Sketch name must not be empty")

    body = resolve_named(doc, body_name, type_id="PartDesign::Body")
    ensure_name_available(doc, name)
    role = _PLANE_ROLES[plane]
    supports = [feature for feature in body.Origin.OriginFeatures if str(feature.Role) == role]
    if len(supports) != 1:
        raise RuntimeError(f"Body origin plane unavailable: {role}")

    created: list[str] = []

    def rollback() -> None:
        for object_name in reversed(created):
            doc.removeObject(object_name)

    with transaction(doc, "Fixture new_sketch", rollback=rollback):
        sketch = body.newObject("Sketcher::SketchObject", name)
        created.append(sketch.Name)
        sketch.Label = name
        sketch.AttachmentSupport = (supports[0], [""])
        sketch.MapMode = "FlatFace"
        doc.recompute()

    return f"created sketch {sketch.Name} in {body.Name} on {plane}"


RUNNER = ToolRunner(name="new_sketch", permission="confirm", run=run)
