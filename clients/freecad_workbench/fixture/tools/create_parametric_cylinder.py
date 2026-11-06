from __future__ import annotations

import math
from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import FreeCAD
    import Part

    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument("Unnamed")

    radius = float(args["radius"])
    height = float(args["height"])
    if not math.isfinite(radius) or not math.isfinite(height):
        raise ValueError("radius and height must be finite")
    if radius <= 0 or height <= 0:
        raise ValueError("radius and height must be > 0")
    name = str(args.get("name") or "Cylinder")

    doc.openTransaction("Fixture create_parametric_cylinder")
    try:
        cyl = Part.makeCylinder(radius, height)
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = cyl
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise

    return f"created {obj.Name} radius={radius} height={height}"


RUNNER = ToolRunner(name="create_parametric_cylinder", permission="confirm", run=run)
