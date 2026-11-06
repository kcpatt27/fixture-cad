"""Blender Path B N1: ambiguous/cross-app no pending; history may stay tool-free."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

ADDON_ROOT = Path(__file__).resolve().parent
if str(ADDON_ROOT) not in sys.path:
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
    print("=== Fixture Blender N1 intent smoke ===", flush=True)
    try:
        import bpy
        from fixture_blender.action_runner import prepare_actions
        from fixture_blender.client import HarnessClient
        from fixture_blender.context import build_context
        from fixture_blender.conversation_history import (
            append_structured_turn,
            format_intent_presentation,
            history_for_request,
        )
    except Exception as exc:
        check("imports", False, str(exc))
        traceback.print_exc()
        return 1

    client = HarnessClient()
    turns: list[dict[str, str]] = []

    def chat(message: str) -> dict:
        nonlocal turns
        history = history_for_request(turns)
        turns = append_structured_turn(turns, role="user", text=message)
        resp = client.send_chat(
            {
                "app": "blender",
                "version": "0.1.0",
                "context": build_context(),
                "message": message,
                "history": history,
                "mode": "chat",
                "model_lane": "accurate",
            }
        )
        turns = append_structured_turn(
            turns, role="assistant", text=str(resp.get("reply_text") or "")
        )
        return resp

    try:
        bpy.ops.wm.read_homefile(use_empty=True)
        before = len(bpy.data.objects)

        cross = chat(
            "Create a parametric interlocking hinge Body with Pad features for 3D printing"
        )
        logs, pending = prepare_actions(cross, defer_confirm=True)
        lines = format_intent_presentation(
            cross.get("intent_status"), cross.get("supported_scope")
        )
        check(
            "cross-app status",
            cross.get("intent_status") in {"ambiguous", "unsupported", "partial"},
            str(cross.get("intent_status")),
        )
        check("cross-app no pending tools", not pending, str(pending))
        check("intent lines present", bool(lines), str(lines[:2]))
        check("mesh unchanged", len(bpy.data.objects) == before, str(bpy.data.objects))
    except Exception as exc:
        check("n1 path", False, str(exc))
        traceback.print_exc()

    print(f"summary: {PASS} pass / {FAIL} fail", flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
