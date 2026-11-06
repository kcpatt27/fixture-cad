from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator


def active_document(*, create: bool = False):
    import FreeCAD

    doc = FreeCAD.ActiveDocument
    if doc is None and create:
        doc = FreeCAD.newDocument("Unnamed")
    if doc is None:
        raise RuntimeError("No active document")
    return doc


def find_named(doc: Any, name: str) -> Any | None:
    """Object by Name, else by unique Label; None when neither matches."""
    obj = doc.getObject(name)
    if obj is None:
        matches = [candidate for candidate in doc.Objects if candidate.Label == name]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous label: {name}")
        obj = matches[0] if matches else None
    return obj


def resolve_named(doc: Any, name: str, *, type_id: str) -> Any:
    obj = find_named(doc, name)
    if obj is None:
        raise RuntimeError(f"Object not found: {name}")
    if not obj.isDerivedFrom(type_id):
        raise RuntimeError(f"{name} is {obj.TypeId}, expected {type_id}")
    return obj


def resolve_named_or_create(
    doc: Any,
    name: str,
    *,
    type_id: str,
    created: list[str] | None = None,
) -> Any:
    """Resolve an object by Name/Label, creating it with that name when absent.

    Used where a plan references a container it may not have created itself
    (e.g. `import_svg_sketch.body_name`): creating the named object keeps the
    plan's identifiers intact instead of failing and forcing a degraded
    re-plan that loses the requested names. Callers wrap this in the runner's
    transaction so the created object is rolled back on failure."""
    obj = find_named(doc, name)
    if obj is None:
        ensure_name_available(doc, name)
        obj = doc.addObject(type_id, name)
        obj.Label = name
        if created is not None:
            created.append(obj.Name)
        return obj
    if not obj.isDerivedFrom(type_id):
        raise RuntimeError(f"{name} is {obj.TypeId}, expected {type_id}")
    return obj


def ensure_name_available(doc: Any, name: str) -> None:
    if doc.getObject(name) is not None or any(obj.Label == name for obj in doc.Objects):
        raise RuntimeError(f"Object name already exists: {name}")


def body_for_sketch(doc: Any, sketch: Any) -> Any:
    parent = None
    if hasattr(sketch, "getParentGeoFeatureGroup"):
        parent = sketch.getParentGeoFeatureGroup()
    if parent is not None and parent.isDerivedFrom("PartDesign::Body"):
        return parent

    for candidate in doc.Objects:
        if not candidate.isDerivedFrom("PartDesign::Body"):
            continue
        if hasattr(candidate, "getObject") and candidate.getObject(sketch.Name) is sketch:
            return candidate
    raise RuntimeError(f"Sketch is not inside a PartDesign Body: {sketch.Name}")


@contextmanager
def transaction(
    doc: Any,
    label: str,
    *,
    rollback: Callable[[], None] | None = None,
) -> Iterator[None]:
    doc.openTransaction(label)
    try:
        yield
        doc.commitTransaction()
    except Exception:
        try:
            if rollback is not None:
                rollback()
                doc.recompute()
        finally:
            doc.abortTransaction()
        raise
