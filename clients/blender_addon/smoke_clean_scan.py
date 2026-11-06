"""Headless smoke: clean_scan repairs an open mesh into a watertight STL."""

from __future__ import annotations

import shutil
import struct
import sys
import tempfile
import traceback
from pathlib import Path

import bpy

ADDON_ROOT = Path(__file__).resolve().parent
if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        line = f"PASS  {name}"
    else:
        FAIL += 1
        line = f"FAIL  {name}"
    if detail:
        line += f"  ({detail})"
    print(line, flush=True)


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def make_open_cube() -> bpy.types.Object:
    bpy.ops.mesh.primitive_cube_add(size=20.0)
    cube = bpy.context.active_object
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(cube.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[0]], context="FACES")
        bm.to_mesh(cube.data)
        cube.data.update()
    finally:
        bm.free()
    return cube


def export_stl(path: Path, obj: bpy.types.Object) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.wm.stl_export(filepath=str(path), export_selected_objects=True)


def binary_stl_triangles(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < 84:
        return 0
    return struct.unpack("<I", data[80:84])[0]


def count_non_manifold(path: Path) -> tuple[int, int]:
    bpy.ops.object.select_all(action="DESELECT")
    bpy.ops.wm.stl_import(filepath=str(path))
    obj = bpy.context.active_object
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        faces = len(bm.faces)
        edges = sum(1 for edge in bm.edges if not edge.is_manifold)
    finally:
        bm.free()
        bpy.data.objects.remove(obj, do_unlink=True)
    return edges, faces


def main() -> int:
    print("=== Fixture clean_scan smoke ===", flush=True)
    print(f"Blender: {bpy.app.version_string}", flush=True)
    tmp = Path(tempfile.mkdtemp(prefix="fixture_clean_scan_"))
    try:
        from fixture_blender.tools.clean_scan import run

        clear_scene()
        src = tmp / "open_cube.stl"
        dst = tmp / "cleaned.stl"
        cube = make_open_cube()
        check("seed open mesh", len(cube.data.polygons) == 5, f"faces={len(cube.data.polygons)}")
        export_stl(src, cube)
        check("temp STL written", src.is_file(), str(src))

        summary = run(
            {
                "input_path": str(src),
                "output_path": str(dst),
                "target_triangles": 1000,
                "fill_holes": True,
                "recalc_normals": True,
                "decimate": True,
            }
        )
        print(f"summary: {summary}", flush=True)
        check("output exists", dst.is_file(), str(dst))
        tris = binary_stl_triangles(dst)
        check("output triangles > 0", tris > 0, f"tris={tris}")
        check("summary watertight", "watertight=True" in summary, summary)
        check(
            "summary no non-manifold edges",
            "non_manifold_edges=0" in summary,
            summary,
        )

        edges, faces = count_non_manifold(dst)
        check(
            "reimported STL watertight",
            faces > 0 and edges == 0,
            f"faces={faces} non_manifold_edges={edges}",
        )
    except Exception as exc:  # noqa: BLE001
        check("smoke body", False, str(exc))
        traceback.print_exc()
    finally:
        clear_scene()
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"summary: {PASS} pass / {FAIL} fail", flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
