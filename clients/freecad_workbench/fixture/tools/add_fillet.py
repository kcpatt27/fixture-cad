from __future__ import annotations

from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import FreeCAD
    import FreeCADGui as Gui
    import Part

    doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active document")

    radius = float(args["radius"])
    object_name = args.get("object_name")
    if object_name:
        obj = doc.getObject(object_name)
    else:
        sel = Gui.Selection.getSelection()
        if not sel:
            raise RuntimeError("Select a solid to fillet")
        obj = sel[0]

    if obj is None or not hasattr(obj, "Shape"):
        raise RuntimeError("Target has no Shape")

    shape = obj.Shape
    edges = list(shape.Edges)
    if not edges:
        raise RuntimeError("No edges to fillet")

    # Limit edges for skeleton safety
    edge_indices = list(range(1, min(len(edges), 12) + 1))

    doc.openTransaction("Fixture add_fillet")
    try:
        fillet = doc.addObject("Part::Fillet", f"{obj.Name}_Fillet")
        fillet.Base = obj
        fillet.Edges = [(i, radius, radius) for i in edge_indices]
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        # Fallback: Part module Fillet on a copy
        doc.openTransaction("Fixture add_fillet_fallback")
        try:
            f = Part.makeFillet(radius, edges[:8])
            out = doc.addObject("Part::Feature", f"{obj.Name}_Fillet")
            out.Shape = f
            doc.recompute()
            doc.commitTransaction()
            return f"filleted via Part.makeFillet → {out.Name}"
        except Exception:
            doc.abortTransaction()
            raise

    return f"filleted {fillet.Name} radius={radius}"


RUNNER = ToolRunner(name="add_fillet", permission="confirm", run=run)
