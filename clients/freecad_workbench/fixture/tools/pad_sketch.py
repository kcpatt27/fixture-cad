from __future__ import annotations

import math
from typing import Any

from ._partdesign import (
    active_document,
    body_for_sketch,
    ensure_name_available,
    resolve_named,
    transaction,
)
from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    doc = active_document()
    sketch_name = str(args["sketch_name"]).strip()
    name = str(args.get("name") or "Pad").strip()
    length = float(args["length"])
    if not math.isfinite(length) or length <= 0:
        raise ValueError("Pad length must be a positive finite number")
    if not name:
        raise ValueError("Pad name must not be empty")

    sketch = resolve_named(doc, sketch_name, type_id="Sketcher::SketchObject")
    body = body_for_sketch(doc, sketch)
    ensure_name_available(doc, name)

    midplane = bool(args.get("midplane", False))
    reversed_direction = bool(args.get("reversed", False))
    created: list[str] = []

    def rollback() -> None:
        for object_name in reversed(created):
            doc.removeObject(object_name)

    with transaction(doc, "Fixture pad_sketch", rollback=rollback):
        pad = body.newObject("PartDesign::Pad", name)
        created.append(pad.Name)
        pad.Label = name
        pad.Profile = sketch
        pad.Length = length
        if "SideType" in pad.PropertiesList:
            pad.SideType = "Symmetric" if midplane else "One side"
        else:
            pad.Midplane = midplane
        pad.Reversed = reversed_direction
        doc.recompute()
        shape = pad.Shape
        if shape.isNull() or len(shape.Solids) != 1:
            raise RuntimeError("Pad did not produce exactly one solid")

    return (
        f"created pad {pad.Name} from {sketch.Name} length={length} "
        f"midplane={midplane} reversed={reversed_direction}"
    )


RUNNER = ToolRunner(name="pad_sketch", permission="confirm", run=run)
