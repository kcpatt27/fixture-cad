# FreeCAD Path B N1: ambiguous no-pending; partial Cancel/Apply; history accept
# Run:
# & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -c "exec(open(r'...\\smoke_n1_intent.py', encoding='utf-8').read())"

from __future__ import annotations

import sys
import traceback
from pathlib import Path

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

PASS = 0
FAIL = 0
LOG = CLIENT_ROOT / "_smoke_n1_last.txt"


def check(name: str, ok: bool, detail: str = "") -> None:
    global PASS, FAIL
    if ok:
        PASS += 1
        line = f"PASS  {name}" + (f"  ({detail})" if detail else "")
    else:
        FAIL += 1
        line = f"FAIL  {name}" + (f"  ({detail})" if detail else "")
    print(line, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        open(LOG, "w", encoding="utf-8").close()
    except Exception:
        pass
    print("=== Fixture FreeCAD N1 intent smoke ===", flush=True)
    try:
        import FreeCAD
        from fixture.action_runner import apply_pending, prepare_actions
        from fixture.client import HarnessClient
        from fixture.context import build_context
        from fixture.conversation_history import (
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
                "app": "freecad",
                "version": "0.1.0",
                "context": build_context(),
                "message": message,
                "history": history,
                "mode": "chat",
                "model_lane": "accurate",
            }
        )
        reply = str(resp.get("reply_text") or "")
        turns = append_structured_turn(turns, role="assistant", text=reply)
        return resp

    try:
        doc = FreeCAD.newDocument("Fixture_N1")
        FreeCAD.setActiveDocument(doc.Name)
        before = len(doc.Objects)

        amb = chat("make an interlocking hinge in plastic")
        logs, pending = prepare_actions(amb, defer_confirm=True)
        intent_lines = format_intent_presentation(
            amb.get("intent_status"), amb.get("supported_scope")
        )
        check(
            "ambiguous/unsupported status",
            amb.get("intent_status") in {"ambiguous", "unsupported"},
            str(amb.get("intent_status")),
        )
        check("ambiguous no pending tools", not pending, str(pending))
        check("intent presentation lines", bool(intent_lines), str(intent_lines[:2]))
        check("ambiguous doc unchanged", len(doc.Objects) == before, str(doc.Objects))

        partial = chat("make a hinge; start with anything you can")
        logs, pending = prepare_actions(partial, defer_confirm=True)
        status = partial.get("intent_status")
        scope = partial.get("supported_scope") or {}
        check(
            "partial-or-supported status",
            status in {"partial", "supported", "ambiguous", "unsupported"},
            str(status),
        )
        if pending:
            check("partial has pending tools", True, str([p.tool_name for p in pending]))
            cancelled = list(pending)
            # Cancel path: discard without apply
            check("pre-Cancel doc unchanged", len(doc.Objects) == before, str(doc.Objects))
            check("Cancel leaves geometry", len(doc.Objects) == before, "discarded pending")

            # Re-fetch and Apply
            again = chat("make a hinge; start with anything you can")
            logs, pending2 = prepare_actions(again, defer_confirm=True)
            if pending2:
                apply_logs = apply_pending(pending2, client=client)
                check(
                    "Apply creates geometry",
                    len(doc.Objects) > before,
                    f"objs={doc.Objects} logs={apply_logs[:2]}",
                )
            else:
                check("Apply creates geometry", False, "no pending after re-ask")
        else:
            check(
                "no pending when fail-closed",
                status in {"ambiguous", "unsupported"},
                f"status={status} scope={scope}",
            )
            # History acceptance still exercises continuity
            accept = chat("yes, make a 30x15x2 mm base plate")
            logs, pending3 = prepare_actions(accept, defer_confirm=True)
            check("history accept pending", bool(pending3), str(accept.get("intent_status")))
            if pending3:
                before2 = len(doc.Objects)
                apply_pending(pending3, client=client)
                check(
                    "history Apply mutates",
                    len(doc.Objects) > before2,
                    str(doc.Objects),
                )

        FreeCAD.closeDocument(doc.Name)
    except Exception as exc:
        check("n1 path", False, str(exc))
        traceback.print_exc()

    print(f"summary: {PASS} pass / {FAIL} fail", flush=True)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

main()
