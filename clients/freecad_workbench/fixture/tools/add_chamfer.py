from __future__ import annotations

import math
from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import FreeCAD
    import FreeCADGui as Gui
    import Part

    doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active document")

    size = float(args["size"])
    if not math.isfinite(size) or size <= 0:
        raise ValueError("size must be a finite number > 0")

    object_name = args.get("object_name")
    if object_name:
        obj = doc.getObject(str(object_name))
        if obj is None:
            matches = [candidate for candidate in doc.Objects if candidate.Label == object_name]
            if len(matches) > 1:
                raise RuntimeError(f"Ambiguous label: {object_name}")
            obj = matches[0] if matches else None
    else:
        sel = Gui.Selection.getSelection()
        if not sel:
            raise RuntimeError("Select a solid to chamfer")
        obj = sel[0]

    if obj is None or not hasattr(obj, "Shape"):
        raise RuntimeError("Target has no Shape")

    shape = obj.Shape
    edges = list(shape.Edges)
    if not edges:
        raise RuntimeError("No edges to chamfer")

    # Limit edges for skeleton safety (mirror add_fillet).
    edge_indices = list(range(1, min(len(edges), 12) + 1))

    doc.openTransaction("Fixture add_chamfer")
    try:
        chamfer = doc.addObject("Part::Chamfer", f"{obj.Name}_Chamfer")
        chamfer.Base = obj
        chamfer.Edges = [(i, size, size) for i in edge_indices]
        doc.recompute()
        if chamfer.Shape.isNull():
            raise RuntimeError("Part::Chamfer produced null shape")
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        doc.openTransaction("Fixture add_chamfer_fallback")
        try:
            out_shape = Part.makeChamfer(size, edges[:8])
            out = doc.addObject("Part::Feature", f"{obj.Name}_Chamfer")
            out.Shape = out_shape
            doc.recompute()
            doc.commitTransaction()
            return f"chamfered via Part.makeChamfer → {out.Name} size={size}"
        except Exception:
            doc.abortTransaction()
            raise

    return f"chamfered {chamfer.Name} size={size}"


RUNNER = ToolRunner(name="add_chamfer", permission="confirm", run=run)
