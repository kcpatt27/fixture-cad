"""Import a scan mesh, clean/repair it, and export an STL.

This is deterministic mesh cleanup, not B-Rep reconstruction. Manifold status is
measured after the fact and reported honestly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .base import ToolRunner

SUPPORTED_INPUT_SUFFIXES = {".stl", ".obj", ".ply"}


def validate_paths(input_path: str, output_path: str) -> tuple[Path, Path]:
    """Validate scan paths without touching bpy (unit-testable)."""
    src = Path(str(input_path)).expanduser().resolve()
    if not src.is_file():
        raise ValueError(f"input_path does not exist: {src}")
    if src.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
        raise ValueError(
            f"unsupported input format {src.suffix!r}; expected .stl, .obj, or .ply"
        )

    dst = Path(str(output_path)).expanduser().resolve()
    if dst.suffix.lower() != ".stl":
        dst = dst.with_suffix(".stl")
    dst.parent.mkdir(parents=True, exist_ok=True)
    return src, dst


def _has_op(namespace: str, op: str) -> bool:
    import bpy

    ns = getattr(bpy.ops, namespace, None)
    return ns is not None and hasattr(ns, op)


def _import_scan(src: Path) -> None:
    suffix = src.suffix.lower()
    filepath = str(src)
    if suffix == ".stl":
        if _has_op("wm", "stl_import"):
            import bpy

            bpy.ops.wm.stl_import(filepath=filepath)
        elif _has_op("import_mesh", "stl"):
            import bpy

            bpy.ops.import_mesh.stl(filepath=filepath)
        else:
            raise RuntimeError("no STL importer available in this Blender build")
    elif suffix == ".obj":
        if _has_op("wm", "obj_import"):
            import bpy

            bpy.ops.wm.obj_import(filepath=filepath)
        elif _has_op("import_scene", "obj"):
            import bpy

            bpy.ops.import_scene.obj(filepath=filepath)
        else:
            raise RuntimeError("no OBJ importer available in this Blender build")
    elif suffix == ".ply":
        if _has_op("wm", "ply_import"):
            import bpy

            bpy.ops.wm.ply_import(filepath=filepath)
        elif _has_op("import_mesh", "ply"):
            import bpy

            bpy.ops.import_mesh.ply(filepath=filepath)
        else:
            raise RuntimeError("no PLY importer available in this Blender build")
    else:
        raise ValueError(f"unsupported input format {suffix!r}")


def _export_stl(dst: Path) -> None:
    import bpy

    if _has_op("wm", "stl_export"):
        bpy.ops.wm.stl_export(filepath=str(dst), export_selected_objects=True)
    elif _has_op("export_mesh", "stl"):
        bpy.ops.export_mesh.stl(filepath=str(dst), use_selection=True)
    else:
        raise RuntimeError("no STL exporter available in this Blender build")


def _find_layer_collection(layer_collection, name: str):
    if layer_collection.collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = _find_layer_collection(child, name)
        if found is not None:
            return found
    return None


def _tri_count(mesh) -> int:
    return sum(max(len(poly.vertices) - 2, 0) for poly in mesh.polygons)


def _non_manifold_edges(mesh) -> tuple[int, int]:
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        faces = len(bm.faces)
        edges = sum(1 for edge in bm.edges if not edge.is_manifold)
    finally:
        bm.free()
    return edges, faces


def _apply_modifier(obj, modifier_name: str) -> None:
    import bpy

    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.modifier_apply(modifier=modifier_name)


def _clean_bmesh(obj, *, merge_distance: float, fill_holes: bool, recalc: bool) -> None:
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        if merge_distance > 0:
            bmesh.ops.remove_doubles(
                bm, verts=list(bm.verts), dist=merge_distance
            )
        if fill_holes:
            boundary = [edge for edge in bm.edges if len(edge.link_faces) == 1]
            if boundary:
                bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
        if recalc:
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        obj.data.update()
    finally:
        bm.free()


def _remove_objects(objects: Iterable) -> None:
    import bpy

    for obj in list(objects):
        if obj is None:
            continue
        mesh = obj.data if obj.type == "MESH" else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)


def run(args: dict[str, Any]) -> str:
    import bpy

    src, dst = validate_paths(args["input_path"], args["output_path"])

    target_triangles = int(args.get("target_triangles") or 50000)
    voxel_size = float(args.get("voxel_size") or 0)
    merge_distance = float(
        args.get("merge_distance")
        if args.get("merge_distance") is not None
        else 0.0001
    )
    fill_holes = bool(args.get("fill_holes", True))
    recalc_normals = bool(args.get("recalc_normals", True))
    decimate = bool(args.get("decimate", True))

    scene = bpy.context.scene
    view_layer = bpy.context.view_layer
    previous_selection = list(bpy.context.selected_objects)
    previous_active = bpy.context.active_object
    previous_mode = previous_active.mode if previous_active is not None else "OBJECT"

    collection = bpy.data.collections.new("FixtureCleanScanTemp")
    scene.collection.children.link(collection)
    imported: list = []
    joined = None
    try:
        if previous_active is not None and previous_active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        layer_collection = _find_layer_collection(
            view_layer.layer_collection, collection.name
        )
        if layer_collection is not None:
            view_layer.active_layer_collection = layer_collection

        _import_scan(src)
        imported = [obj for obj in collection.objects if obj.type == "MESH"]
        if not imported:
            raise RuntimeError(f"no mesh objects imported from {src}")

        bpy.ops.object.select_all(action="DESELECT")
        for obj in imported:
            obj.select_set(True)
        joined = imported[0]
        view_layer.objects.active = joined
        if len(imported) > 1:
            bpy.ops.object.join()
        imported = [joined]
        joined.select_set(True)

        before_tris = _tri_count(joined.data)
        _clean_bmesh(
            joined,
            merge_distance=merge_distance,
            fill_holes=fill_holes,
            recalc=recalc_normals,
        )

        if voxel_size > 0:
            remesh = joined.modifiers.new("FixtureVoxelRemesh", "REMESH")
            remesh.mode = "VOXEL"
            remesh.voxel_size = voxel_size
            _apply_modifier(joined, remesh.name)

        if decimate:
            current_tris = _tri_count(joined.data)
            if current_tris > target_triangles > 0:
                ratio = max(target_triangles / current_tris, 0.001)
                decimator = joined.modifiers.new("FixtureDecimate", "DECIMATE")
                decimator.decimate_type = "COLLAPSE"
                decimator.ratio = min(ratio, 1.0)
                decimator.use_collapse_triangulate = True
                _apply_modifier(joined, decimator.name)

        after_tris = _tri_count(joined.data)
        non_manifold, faces = _non_manifold_edges(joined.data)
        watertight = faces > 0 and non_manifold == 0

        bpy.ops.object.select_all(action="DESELECT")
        joined.select_set(True)
        view_layer.objects.active = joined
        _export_stl(dst)
    finally:
        _remove_objects(imported)
        if joined is not None and joined not in imported:
            _remove_objects([joined])
        if collection.name in bpy.data.collections:
            try:
                bpy.data.collections.remove(collection)
            except ReferenceError:
                pass

        try:
            view_layer.active_layer_collection = _find_layer_collection(
                view_layer.layer_collection, scene.collection.name
            ) or view_layer.layer_collection
        except Exception:  # noqa: BLE001
            pass

        for obj in previous_selection:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if previous_active is not None and previous_active.name in bpy.data.objects:
            view_layer.objects.active = previous_active
            if previous_mode in {"OBJECT", "EDIT"}:
                try:
                    bpy.ops.object.mode_set(mode=previous_mode)
                except Exception:  # noqa: BLE001
                    pass

    return (
        f"clean_scan: in={before_tris} tris out={after_tris} tris "
        f"watertight={watertight} non_manifold_edges={non_manifold} out={dst}"
    )


RUNNER = ToolRunner(name="clean_scan", permission="confirm", run=run)
