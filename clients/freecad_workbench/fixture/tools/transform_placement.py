from __future__ import annotations

import math
from typing import Any

from .base import ToolRunner


def run(args: dict[str, Any]) -> str:
    import FreeCAD

    doc = FreeCAD.ActiveDocument
    if doc is None:
        raise RuntimeError("No active document")

    object_name = str(args["object_name"]).strip()
    if not object_name:
        raise ValueError("object_name is required")

    transform_keys = ("x", "y", "z", "rx", "ry", "rz")
    provided = {key: args[key] for key in transform_keys if key in args and args[key] is not None}
    if not provided:
        raise ValueError("at least one of x,y,z,rx,ry,rz is required")

    for key, raw in provided.items():
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError(f"{key} must be finite")
        provided[key] = value

    obj = doc.getObject(object_name)
    if obj is None:
        matches = [candidate for candidate in doc.Objects if candidate.Label == object_name]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous label: {object_name}")
        obj = matches[0] if matches else None
    if obj is None:
        raise RuntimeError(f"Object not found: {object_name}")
    if not hasattr(obj, "Placement"):
        raise RuntimeError(f"{object_name} has no Placement")

    placement = FreeCAD.Placement(obj.Placement)
    base = FreeCAD.Vector(placement.Base)
    if "x" in provided:
        base.x = provided["x"]
    if "y" in provided:
        base.y = provided["y"]
    if "z" in provided:
        base.z = provided["z"]

    rotation = placement.Rotation
    if any(key in provided for key in ("rx", "ry", "rz")):
        # FreeCAD.Rotation(yaw, pitch, roll) uses degrees: yaw=Z, pitch=Y, roll=X.
        yaw = pitch = roll = 0.0
        getter = getattr(rotation, "getYawPitchRoll", None)
        if callable(getter):
            yaw, pitch, roll = getter()
        if "rz" in provided:
            yaw = provided["rz"]
        if "ry" in provided:
            pitch = provided["ry"]
        if "rx" in provided:
            roll = provided["rx"]
        rotation = FreeCAD.Rotation(yaw, pitch, roll)

    doc.openTransaction("Fixture transform_placement")
    try:
        obj.Placement = FreeCAD.Placement(base, rotation)
        doc.recompute()
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        raise

    parts = [f"{key}={provided[key]}" for key in transform_keys if key in provided]
    return f"placed {obj.Name} {' '.join(parts)}"


RUNNER = ToolRunner(name="transform_placement", permission="confirm", run=run)
