"""Blender Path B smoke: harness chat, pending confirmation, Cancel, then Apply."""

from __future__ import annotations

import json
import os
import sys
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


def tool_names(response: dict) -> list[str]:
    return [
        action.get("tool_name")
        for action in response.get("actions") or []
        if action.get("type") == "tool_call"
    ]


def has_need_confirm(response: dict) -> bool:
    return any(
        action.get("type") == "meta" and action.get("kind") == "need_confirm"
        for action in response.get("actions") or []
    )


def create_duplicate_mesh() -> bpy.types.Object:
    mesh = bpy.data.meshes.new("FixtureSmokeMesh")
    mesh.from_pydata(
        [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        [],
        [(0, 2, 3), (1, 2, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new("FixtureSmokeObject", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj


def main() -> int:
    print("=== Fixture Blender smoke (chat -> Cancel / Apply) ===", flush=True)
    print(f"Blender: {bpy.app.version_string}", flush=True)

    import fixture_blender
    from fixture_blender import config, operators
    from fixture_blender.action_runner import prepare_actions
    from fixture_blender.client import HarnessClient
    from fixture_blender.context import build_context

    registered = False
    obj: bpy.types.Object | None = None
    try:
        # Addon may already be enabled in Blender user prefs.
        if not hasattr(bpy.types.Scene, "fixture"):
            fixture_blender.register()
            registered = True
        check(
            "addon register",
            hasattr(bpy.types.Scene, "fixture")
            and hasattr(bpy.ops.fixture, "apply")
            and hasattr(bpy.ops.fixture, "cancel"),
        )

        client = HarnessClient(timeout=180.0)
        health = client.health()
        check("harness /health", bool(health.get("ok")), json.dumps(health)[:160])
        expected_model = os.environ.get(
            "FIXTURE_SMOKE_MODEL", "qwen2.5:14b-instruct-q4_K_M"
        )
        check(
            "harness model pin",
            health.get("model") == expected_model,
            str(health.get("model")),
        )

        obj = create_duplicate_mesh()
        check("seed duplicate mesh", len(obj.data.vertices) == 4, "vertices=4")
        response = client.send_chat(
            {
                "app": config.PROTOCOL_APP,
                "version": config.CLIENT_VERSION,
                "context": build_context(),
                "message": "Clean the selected mesh by merging vertices within 0.0001 meters.",
                "mode": "chat",
            }
        )
        tools = tool_names(response)
        check(
            "chat clean -> clean_mesh",
            "clean_mesh" in tools,
            f"tools={tools} reply={(response.get('reply_text') or '')[:60]}",
        )
        check("chat clean need_confirm", has_need_confirm(response), "meta need_confirm")

        logs, pending = prepare_actions(response, client=client, defer_confirm=True)
        check(
            "clean deferred",
            len(pending) == 1 and pending[0].tool_name == "clean_mesh",
            f"logs={logs} pending={pending}",
        )
        check("pre-confirm unchanged", len(obj.data.vertices) == 4, "vertices=4")

        operators._set_pending(pending, response.get("request_id"))
        cancel_result = bpy.ops.fixture.cancel()
        check(
            "Cancel keeps mesh unchanged",
            cancel_result == {"FINISHED"}
            and not operators.has_pending_tools()
            and len(obj.data.vertices) == 4,
            f"result={cancel_result} vertices={len(obj.data.vertices)}",
        )

        operators._set_pending(pending, response.get("request_id"))
        apply_result = bpy.ops.fixture.apply()
        check(
            "Apply cleans mesh",
            apply_result == {"FINISHED"}
            and not operators.has_pending_tools()
            and len(obj.data.vertices) == 3,
            (
                f"result={apply_result} vertices={len(obj.data.vertices)} "
                f"transcript={operators.get_transcript()}"
            ),
        )
    except Exception as exc:
        check("smoke body", False, str(exc))
        traceback.print_exc()
    finally:
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
        if registered:
            fixture_blender.unregister()

    print(f"summary: {PASS} pass / {FAIL} fail", flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
