from __future__ import annotations

from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import FreeCAD
    import Part

    doc = FreeCAD.ActiveDocument
    if doc is None:
        doc = FreeCAD.newDocument("Unnamed")

    width = float(args["width"])
    height = float(args["height"])
    depth = float(args["depth"])
    name = str(args.get("name") or "Box")

    doc.openTransaction("Fixture create_parametric_box")
    try:
        box = Part.makeBox(width, height, depth)
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = box
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise

    return f"created {obj.Name} {width}x{height}x{depth}"


RUNNER = ToolRunner(name="create_parametric_box", permission="confirm", run=run)
