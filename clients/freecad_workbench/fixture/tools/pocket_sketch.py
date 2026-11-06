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


def _source_solid_volume(body: Any, sketch: Any) -> float:
    source_volume = 0.0
    for feature in getattr(body, "Group", []):
        if feature is sketch:
            break
        shape = getattr(feature, "Shape", None)
        if shape is None or shape.isNull() or len(shape.Solids) != 1:
            continue
        volume = float(shape.Volume)
        if math.isfinite(volume) and volume > 0:
            source_volume = volume
    if source_volume <= 0:
        raise RuntimeError("Pocket requires exactly one existing Body solid")
    return source_volume


def run(args: dict[str, Any]) -> str:
    doc = active_document()
    sketch_name = str(args["sketch_name"]).strip()
    name = str(args.get("name") or "Pocket").strip()
    length = float(args["length"])
    if not math.isfinite(length) or length <= 0:
        raise ValueError("Pocket length must be a positive finite number")
    if not name:
        raise ValueError("Pocket name must not be empty")

    sketch = resolve_named(doc, sketch_name, type_id="Sketcher::SketchObject")
    body = body_for_sketch(doc, sketch)
    ensure_name_available(doc, name)
    source_volume = _source_solid_volume(body, sketch)

    reversed_direction = bool(args.get("reversed", False))
    created: list[str] = []

    def rollback() -> None:
        for object_name in reversed(created):
            doc.removeObject(object_name)

    with transaction(doc, "Fixture pocket_sketch", rollback=rollback):
        pocket = body.newObject("PartDesign::Pocket", name)
        created.append(pocket.Name)
        pocket.Label = name
        pocket.Profile = sketch
        pocket.Length = length
        pocket.Reversed = reversed_direction
        doc.recompute()
        shape = pocket.Shape
        if shape.isNull() or len(shape.Solids) != 1:
            raise RuntimeError("Pocket did not produce exactly one solid")
        result_volume = float(shape.Volume)
        if not math.isfinite(result_volume) or result_volume >= source_volume:
            raise RuntimeError("Pocket did not reduce the Body solid volume")

    return (
        f"created pocket {pocket.Name} from {sketch.Name} length={length} "
        f"reversed={reversed_direction}"
    )


RUNNER = ToolRunner(name="pocket_sketch", permission="confirm", run=run)
