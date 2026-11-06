from __future__ import annotations

from typing import Any

from ..reference_store import get_store
from ._partdesign import (
    active_document,
    ensure_name_available,
    resolve_named_or_create,
    transaction,
)
from .base import ToolRunner

MAX_PATHS = 64
MAX_EDGES = 512


def _edge_to_geometry(edge: Any) -> Any | None:
    import Part

    if edge is None or edge.isNull():
        return None
    curve = edge.Curve
    type_id = getattr(curve, "TypeId", "") or type(curve).__name__

    if "Line" in type_id:
        verts = edge.Vertexes
        if len(verts) < 2:
            return None
        return Part.LineSegment(verts[0].Point, verts[1].Point)
    if "Circle" in type_id:
        first = float(edge.FirstParameter)
        last = float(edge.LastParameter)
        # Full circle vs arc
        span = abs(last - first)
        if span >= 6.28:  # ~2*pi
            return Part.Circle(curve.Center, curve.Axis, curve.Radius)
        return Part.ArcOfCircle(curve, first, last)
    if "BSpline" in type_id or "Bezier" in type_id:
        try:
            return curve.toBSpline(edge.FirstParameter, edge.LastParameter)
        except Exception:  # noqa: BLE001
            return None
    try:
        return edge.Curve.toBSpline(edge.FirstParameter, edge.LastParameter)
    except Exception:  # noqa: BLE001
        return None


def _collect_svg_edges(svg_path: str) -> tuple[list[Any], int]:
    import FreeCAD
    import importSVG

    previous = FreeCAD.ActiveDocument
    tmp_name = "_Fixture_SVG_Import"
    # Close leftover temp doc if a prior failure left one open.
    if tmp_name in FreeCAD.listDocuments():
        FreeCAD.closeDocument(tmp_name)
    tmp = FreeCAD.newDocument(tmp_name)
    try:
        importSVG.insert(str(svg_path), tmp.Name)
        edges: list[Any] = []
        path_count = 0
        for obj in list(tmp.Objects):
            shape = getattr(obj, "Shape", None)
            if shape is None or shape.isNull():
                continue
            path_count += 1
            if path_count > MAX_PATHS:
                raise RuntimeError(
                    f"SVG exceeds path cap ({MAX_PATHS}); simplify the file"
                )
            for edge in shape.Edges:
                edges.append(edge.copy())
                if len(edges) > MAX_EDGES:
                    raise RuntimeError(
                        f"SVG exceeds edge cap ({MAX_EDGES}); simplify the file"
                    )
        if not edges:
            raise RuntimeError("SVG produced no edges")
        return edges, path_count
    finally:
        FreeCAD.closeDocument(tmp.Name)
        if previous is not None and previous.Name in FreeCAD.listDocuments():
            FreeCAD.setActiveDocument(previous.Name)
            try:
                FreeCAD.ActiveDocument = previous
            except Exception:  # noqa: BLE001
                pass


def run(args: dict[str, Any]) -> str:
    store = get_store()
    svg_path = store.consume_svg_path()
    # Collect edges first (may briefly switch ActiveDocument to a temp doc).
    edges, path_count = _collect_svg_edges(str(svg_path))

    doc = active_document(create=True)
    sketch_name = str(args.get("name") or "ImportedSketch").strip()
    if not sketch_name:
        raise ValueError("Sketch name must not be empty")
    ensure_name_available(doc, sketch_name)

    body_name_arg = args.get("body_name")
    created: list[str] = []

    def rollback() -> None:
        for object_name in reversed(created):
            obj = doc.getObject(object_name)
            if obj is not None:
                doc.removeObject(object_name)

    with transaction(doc, "Fixture import_svg_sketch", rollback=rollback):
        if body_name_arg:
            # create-or-reuse: a plan may name a body it did not create itself
            body = resolve_named_or_create(
                doc, str(body_name_arg).strip(), type_id="PartDesign::Body", created=created
            )
        else:
            body_label = f"{sketch_name}_Body"
            ensure_name_available(doc, body_label)
            body = doc.addObject("PartDesign::Body", body_label)
            body.Label = body_label
            created.append(body.Name)

        supports = [
            feature
            for feature in body.Origin.OriginFeatures
            if str(feature.Role) == "XY_Plane"
        ]
        if len(supports) != 1:
            raise RuntimeError("Body origin XY plane unavailable")

        sketch = body.newObject("Sketcher::SketchObject", sketch_name)
        created.append(sketch.Name)
        sketch.Label = sketch_name
        sketch.AttachmentSupport = (supports[0], [""])
        sketch.MapMode = "FlatFace"

        added = 0
        for edge in edges:
            geom = _edge_to_geometry(edge)
            if geom is None:
                continue
            sketch.addGeometry(geom, False)
            added += 1
        if added < 1:
            raise RuntimeError("No sketch geometry could be created from SVG edges")
        doc.recompute()

    return (
        f"imported sketch {sketch.Name} ({added} edges from {svg_path.name}; "
        f"{path_count} paths)"
    )


RUNNER = ToolRunner(name="import_svg_sketch", permission="confirm", run=run)
