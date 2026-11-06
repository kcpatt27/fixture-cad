"""Blender Path B N2: post-Apply verify after clean_mesh."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ADDON_ROOT = Path(__file__).resolve().parent
# Prefer repo sources over any previously installed addon package.
for key in list(sys.modules):
    if key == "fixture_blender" or key.startswith("fixture_blender."):
        del sys.modules[key]
sys.path.insert(0, str(ADDON_ROOT))

PASS = 0
FAIL = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"PASS  {name}" + (f"  ({detail})" if detail else ""), flush=True)
    else:
        FAIL += 1
        print(f"FAIL  {name}" + (f"  ({detail})" if detail else ""), flush=True)


def main() -> int:
    print("=== Fixture Blender N2 verify smoke ===", flush=True)
    try:
        import bpy
        from fixture_blender.action_runner import apply_pending, prepare_actions
        from fixture_blender.client import HarnessClient
        from fixture_blender.context import build_context
        from fixture_blender.tools.clean_mesh import run as clean_mesh
        from fixture_blender.verify import (
            VERIFY_MESSAGE,
            filter_verify_response,
            post_apply_verify,
        )
    except Exception as exc:
        check("imports", False, str(exc))
        traceback.print_exc()
        return 1

    try:
        bpy.ops.wm.read_homefile(use_empty=True)
        mesh = bpy.data.meshes.new("N2Mesh")
        # Four verts with a duplicate pair so clean_mesh merges.
        mesh.from_pydata(
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.0, 0.0, 0.0)],
            [],
            [(0, 1, 2)],
        )
        obj = bpy.data.objects.new("N2Cube", mesh)
        bpy.context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        before_verts = len(obj.data.vertices)

        result = clean_mesh({"merge_distance": 0.0001})
        check("clean_mesh ran", "cleaned" in result, result)
        after_verts = len(obj.data.vertices)
        check("verts reduced", after_verts < before_verts, f"{before_verts}->{after_verts}")

        logs = [f"ok: clean_mesh -> {result}"]
        verify_lines, inspection = post_apply_verify(logs)
        check("verify lines", any(ln.startswith("verify:") for ln in verify_lines), str(verify_lines[:3]))
        check(
            "inspection has verts",
            "verts=" in str(inspection.get("detail") or "")
            or any("vertices" in (e or {}) for e in (inspection.get("selected") or [])),
            str(inspection.get("detail") or "")[:120],
        )

        client = HarnessClient()
        context = build_context()
        extra = dict(context.get("extra") or {})
        extra["inspection"] = inspection
        context["extra"] = extra
        resp = client.send_chat(
            {
                "app": "blender",
                "version": "0.1.0",
                "context": context,
                "message": VERIFY_MESSAGE,
                "history": [],
                "mode": "explain",
                "model_lane": "accurate",
            }
        )
        filtered = filter_verify_response(resp)
        _logs, pending = prepare_actions(filtered, defer_confirm=True)
        check("verify reply", bool(str(filtered.get("reply_text") or "").strip()))
        check("verify no confirm pending", not pending, str(pending))

        # Chat -> pending -> Apply path
        bpy.ops.wm.read_homefile(use_empty=True)
        mesh2 = bpy.data.meshes.new("SmokeMesh")
        mesh2.from_pydata(
            [(0, 0, 0), (1, 0, 0), (0, 1, 0), (0.0, 0.0, 0.0)],
            [],
            [(0, 1, 2)],
        )
        obj2 = bpy.data.objects.new("SmokeCube", mesh2)
        bpy.context.collection.objects.link(obj2)
        bpy.context.view_layer.objects.active = obj2
        obj2.select_set(True)
        plan = client.send_chat(
            {
                "app": "blender",
                "version": "0.1.0",
                "context": build_context(),
                "message": "clean this mesh merge distance 0.0001",
                "history": [],
                "mode": "chat",
                "model_lane": "accurate",
            }
        )
        _logs2, pending2 = prepare_actions(plan, defer_confirm=True)
        check("clean pending", bool(pending2), str([p.tool_name for p in pending2]))
        if pending2:
            apply_logs = apply_pending(pending2, client=client)
            v_lines, _insp = post_apply_verify(apply_logs)
            check(
                "Apply verify lines",
                any(ln.startswith("verify:") for ln in v_lines),
                str(v_lines[:2]),
            )

    except Exception as exc:
        check("smoke body", False, str(exc))
        traceback.print_exc()

    print(f"=== {PASS} pass / {FAIL} fail ===", flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
