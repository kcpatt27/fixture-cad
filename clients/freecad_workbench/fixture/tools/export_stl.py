from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ._partdesign import active_document, transaction
from .base import ToolRunner

_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]+\.stl$")


def _export_dir(doc: Any) -> Path:
    import FreeCAD

    file_name = getattr(doc, "FileName", "") or ""
    if file_name:
        base = Path(file_name).expanduser().resolve().parent
    else:
        base = Path(FreeCAD.getUserAppDataDir()).expanduser().resolve()
    target = base / "fixture_exports"
    target.mkdir(parents=True, exist_ok=True)
    return target


def _solid_objects(doc: Any) -> list[Any]:
    solids: list[Any] = []
    for obj in doc.Objects:
        shape = getattr(obj, "Shape", None)
        if shape is None or shape.isNull():
            continue
        try:
            if len(shape.Solids) >= 1:
                solids.append(obj)
        except Exception:  # noqa: BLE001
            continue
    return solids


def _resolve_export_object(doc: Any, name: str) -> Any:
    obj = doc.getObject(name)
    if obj is None:
        matches = [candidate for candidate in doc.Objects if candidate.Label == name]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous label: {name}")
        obj = matches[0] if matches else None
    if obj is None:
        raise RuntimeError(f"Object not found: {name}")
    return obj


def run(args: dict[str, Any]) -> str:
    import Mesh

    doc = active_document()
    filename = str(args.get("path") or "export.stl").strip()
    if not _FILENAME_RE.fullmatch(filename):
        raise ValueError(
            "path must be a filename only matching [A-Za-z0-9_.-]+.stl "
            "(no directories or separators)"
        )

    names = args.get("object_names")
    if names:
        objects = [_resolve_export_object(doc, str(name).strip()) for name in names]
        for obj in objects:
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull() or len(shape.Solids) < 1:
                raise RuntimeError(f"{obj.Name} has no solid to export")
    else:
        objects = _solid_objects(doc)
        if not objects:
            raise RuntimeError("No solids in the active document to export")

    out_path = _export_dir(doc) / filename
    with transaction(doc, "Fixture export_stl"):
        Mesh.export(objects, str(out_path))

    if not out_path.is_file() or out_path.stat().st_size < 1:
        raise RuntimeError(f"STL export produced no file: {out_path}")
    names_joined = ", ".join(obj.Name for obj in objects)
    return f"exported STL {out_path} ({names_joined})"


RUNNER = ToolRunner(name="export_stl", permission="confirm", run=run)
