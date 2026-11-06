from __future__ import annotations

import math
from typing import Any

from ._partdesign import active_document, resolve_named, transaction
from .base import ToolRunner


def _number(args: dict[str, Any], name: str, default: float | None = None) -> float:
    raw = args.get(name, default)
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def run(args: dict[str, Any]) -> str:
    import FreeCAD
    import Part
    import Sketcher

    doc = active_document()
    sketch_name = str(args["sketch_name"]).strip()
    sketch = resolve_named(doc, sketch_name, type_id="Sketcher::SketchObject")
    if int(sketch.GeometryCount) != 0:
        raise RuntimeError("sketch_rectangle requires an empty sketch")

    x = _number(args, "x", 0.0)
    y = _number(args, "y", 0.0)
    width = _number(args, "width")
    height = _number(args, "height")
    if width <= 0 or height <= 0:
        raise ValueError("Rectangle width and height must be positive")

    points = (
        FreeCAD.Vector(x, y, 0),
        FreeCAD.Vector(x + width, y, 0),
        FreeCAD.Vector(x + width, y + height, 0),
        FreeCAD.Vector(x, y + height, 0),
    )
    segments = (
        Part.LineSegment(points[0], points[1]),
        Part.LineSegment(points[1], points[2]),
        Part.LineSegment(points[2], points[3]),
        Part.LineSegment(points[3], points[0]),
    )

    indices: list[int] = []

    def rollback() -> None:
        for index in reversed(indices):
            if index < int(sketch.GeometryCount):
                sketch.delGeometry(index)

    with transaction(doc, "Fixture sketch_rectangle", rollback=rollback):
        indices.extend(sketch.addGeometry(segment, False) for segment in segments)
        constraints = [
            Sketcher.Constraint("Horizontal", indices[0]),
            Sketcher.Constraint("Vertical", indices[1]),
            Sketcher.Constraint("Horizontal", indices[2]),
            Sketcher.Constraint("Vertical", indices[3]),
            Sketcher.Constraint("Coincident", indices[0], 2, indices[1], 1),
            Sketcher.Constraint("Coincident", indices[1], 2, indices[2], 1),
            Sketcher.Constraint("Coincident", indices[2], 2, indices[3], 1),
            Sketcher.Constraint("Coincident", indices[3], 2, indices[0], 1),
        ]
        sketch.addConstraint(constraints)
        doc.recompute()

    return (
        f"added rectangle to {sketch.Name} "
        f"x={x} y={y} width={width} height={height}"
    )


RUNNER = ToolRunner(name="sketch_rectangle", permission="confirm", run=run)
