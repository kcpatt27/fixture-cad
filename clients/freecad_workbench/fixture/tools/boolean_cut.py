from __future__ import annotations

from typing import Any

from .base import ToolRunner
from ._partdesign import active_document, ensure_name_available, transaction


def _resolve_shape_object(doc: Any, name: str) -> Any:
    obj = doc.getObject(name)
    if obj is None:
        matches = [candidate for candidate in doc.Objects if candidate.Label == name]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous label: {name}")
        obj = matches[0] if matches else None
    if obj is None:
        raise RuntimeError(f"Object not found: {name}")
    if not hasattr(obj, "Shape") or obj.Shape is None or obj.Shape.isNull():
        raise RuntimeError(f"{name} has no solid Shape")
    return obj


def run(args: dict[str, Any]) -> str:
    doc = active_document(create=False)
    base_name = str(args["base_name"]).strip()
    tool_name = str(args["tool_name"]).strip()
    if not base_name or not tool_name:
        raise ValueError("base_name and tool_name are required")
    if base_name == tool_name:
        raise ValueError("base_name and tool_name must differ")

    base = _resolve_shape_object(doc, base_name)
    tool = _resolve_shape_object(doc, tool_name)
    name = str(args.get("name") or f"{base.Name}_Cut").strip()
    ensure_name_available(doc, name)

    created: list[str] = []

    def rollback() -> None:
        for obj_name in reversed(created):
            obj = doc.getObject(obj_name)
            if obj is not None:
                doc.removeObject(obj_name)

    with transaction(doc, "Fixture boolean_cut", rollback=rollback):
        cut = doc.addObject("Part::Cut", name)
        created.append(cut.Name)
        cut.Base = base
        cut.Tool = tool
        doc.recompute()
        shape = cut.Shape
        if shape.isNull() or len(shape.Solids) < 1:
            raise RuntimeError("boolean_cut did not produce a solid")

    return f"cut {cut.Name} = {base.Name} minus {tool.Name}"


RUNNER = ToolRunner(name="boolean_cut", permission="confirm", run=run)
