# FreeCAD headless smoke for Fixture
# Run: "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" -c "exec(open(r'...\\smoke_freecad.py', encoding='utf-8').read())"

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

PASS = 0
FAIL = 0

CLIENT_ROOT = Path(__file__).resolve().parent
if str(CLIENT_ROOT) not in sys.path:
    sys.path.insert(0, str(CLIENT_ROOT))

_DEFAULT_LOG = CLIENT_ROOT / "_smoke_last.txt"
LOG_PATH = Path(os.environ.get("FIXTURE_SMOKE_LOG", str(_DEFAULT_LOG)))


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
        with open(LOG_PATH, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def main() -> int:
    log_path = LOG_PATH
    try:
        open(log_path, "w", encoding="utf-8").close()
    except Exception:
        pass
    print("=== Fixture FreeCAD smoke ===", flush=True)
    try:
        import FreeCAD as App

        print("FreeCAD:", ".".join(str(x) for x in App.Version()[:3]))
    except Exception as exc:
        print("FreeCAD version lookup failed:", exc)

    # Mod junction should put package importable as fixture
    try:
        import fixture
        from fixture import config
        from fixture.client import HarnessClient
        from fixture.context import build_context
        from fixture.tools.create_parametric_box import run as run_box
        from fixture.tools.explain_selection import run as run_explain

        check("import fixture", True, getattr(fixture, "__version__", "?"))
        check("config app", config.PROTOCOL_APP == "freecad", config.PROTOCOL_APP)
    except Exception as exc:
        check("import fixture", False, str(exc))
        traceback.print_exc()
        print(f"summary: {PASS} pass / {FAIL} fail")
        return 1

    # Local tool: create box (no harness needed)
    try:
        import FreeCAD

        doc = FreeCAD.newDocument("Fixture_Smoke")
        FreeCAD.setActiveDocument(doc.Name)
        msg = run_box({"width": 40, "height": 40, "depth": 10, "name": "SmokeBox"})
        obj = doc.getObject("SmokeBox")
        check("create_parametric_box", obj is not None, msg)
        explain = run_explain({})
        check("explain_selection local", "SmokeBox" in explain, explain[:120])
        FreeCAD.closeDocument(doc.Name)
        sys.stdout.flush()
    except Exception as exc:
        check("create_parametric_box", False, str(exc))
        traceback.print_exc()

    # Harness health + explain chat (needs Ollama + harness or at least port)
    try:
        client = HarnessClient(timeout=180.0)
        health = client.health()
        check("harness /health", bool(health.get("ok")), json.dumps(health)[:120])
        ctx = {
            "active_document": "Smoke",
            "workbench_or_mode": "Part",
            "selected_objects": [
                {"name": "Pad001", "type": "PartDesign::Pad", "shape": "Solid", "properties": {"Length": 10}}
            ],
            "extra": {},
        }
        resp = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": ctx,
                "message": "Explain what this selected part is",
                "mode": "explain",
            }
        )
        check(
            "harness /chat explain",
            isinstance(resp.get("reply_text"), str) and "actions" in resp,
            (resp.get("reply_text") or "")[:80],
        )
        tools = [
            a.get("tool_name")
            for a in (resp.get("actions") or [])
            if a.get("type") == "tool_call"
        ]
        check(
            "harness suggest tool or reply",
            True,  # soft: model may reply-only
            f"tools={tools}",
        )
    except Exception as exc:
        check("harness path", False, str(exc))
        print("  (start harness on :8766 with pinned model if this fails)")

    summary = f"summary: {PASS} pass / {FAIL} fail"
    print(summary, flush=True)
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")
    except Exception:
        pass
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
