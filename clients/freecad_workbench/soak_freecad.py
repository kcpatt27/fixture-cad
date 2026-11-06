# Fixture FreeCAD soak: harness chat → pending Apply → tool exec
# Exercises explain / fit / fillet with the same defer_confirm path as the chat dock.
# Run:
#   & "C:\Program Files\FreeCAD 1.1\bin\freecadcmd.exe" `
#     -c "exec(open(r'...\clients\freecad_workbench\soak_freecad.py', encoding='utf-8').read())"

from __future__ import annotations

import json
import traceback
from pathlib import Path

PASS = 0
FAIL = 0
LOG = Path(__file__).resolve().parent / "_soak_last.txt"


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


def _tool_names(resp: dict) -> list[str]:
    return [
        a.get("tool_name")
        for a in (resp.get("actions") or [])
        if a.get("type") == "tool_call"
    ]


def _has_need_confirm(resp: dict) -> bool:
    return any(
        a.get("type") == "meta" and a.get("kind") == "need_confirm"
        for a in (resp.get("actions") or [])
    )


def main() -> int:
    try:
        open(LOG, "w", encoding="utf-8").close()
    except Exception:
        pass

    print("=== Fixture FreeCAD soak (chat->Apply) ===", flush=True)
    try:
        import FreeCAD as App

        print("FreeCAD:", ".".join(str(x) for x in App.Version()[:3]), flush=True)
    except Exception as exc:
        print("version:", exc, flush=True)

    try:
        from fixture import config
        from fixture.action_runner import apply_pending, prepare_actions
        from fixture.client import HarnessClient
        from fixture.tools.create_parametric_box import run as run_box
    except Exception as exc:
        check("import fixture", False, str(exc))
        traceback.print_exc()
        return 1

    client = HarnessClient(timeout=180.0)
    try:
        health = client.health()
        check(
            "harness /health",
            bool(health.get("ok")),
            json.dumps(health)[:160],
        )
        check(
            "harness model pin",
            health.get("model") == "qwen2.5:14b-instruct-q4_K_M",
            str(health.get("model")),
        )
    except Exception as exc:
        check("harness /health", False, str(exc))
        return 1

    import FreeCAD

    doc = FreeCAD.newDocument("Fixture_Soak")
    FreeCAD.setActiveDocument(doc.Name)
    try:
        msg = run_box({"width": 40, "height": 40, "depth": 10, "name": "SoakBox"})
        obj = doc.getObject("SoakBox")
        check("seed box", obj is not None, msg)

        try:
            import FreeCADGui as Gui

            if not hasattr(Gui, "Selection"):
                raise RuntimeError("FreeCADGui.Selection unavailable (headless)")
            Gui.Selection.clearSelection()
            Gui.Selection.addSelection(doc.Name, "SoakBox")
            check("select SoakBox", True)
            gui_ok = True
        except Exception as exc:
            check("select SoakBox (headless ok)", True, f"no Gui: {exc}")
            gui_ok = False

        ctx = {
            "active_document": doc.Name,
            "workbench_or_mode": "Fixture",
            "selected_objects": [
                {
                    "name": "SoakBox",
                    "type": "Part::Box",
                    "shape": "Solid",
                    "properties": {"Length": 40, "Width": 40, "Height": 10},
                }
            ],
            "extra": {},
        }

        # --- explain (auto) ---
        resp = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": ctx,
                "message": "Explain the selected object",
                "mode": "explain",
            }
        )
        tools = _tool_names(resp)
        check(
            "chat explain -> explain_selection",
            "explain_selection" in tools,
            f"tools={tools} reply={(resp.get('reply_text') or '')[:60]}",
        )
        logs, pending = prepare_actions(resp, client=client, defer_confirm=True)
        check("explain pending empty", not pending, f"pending={pending}")
        check(
            "explain auto-ran",
            any("ok: explain_selection" in line for line in logs),
            "; ".join(logs)[:160],
        )

        # --- fit (auto) ---
        resp = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": ctx,
                "message": "Fit the view to the selection",
                "mode": "chat",
            }
        )
        tools = _tool_names(resp)
        check(
            "chat fit -> fit_view_selection",
            "fit_view_selection" in tools,
            f"tools={tools}",
        )
        logs, pending = prepare_actions(resp, client=client, defer_confirm=True)
        if gui_ok:
            check(
                "fit auto-ran",
                any("ok: fit_view_selection" in line for line in logs),
                "; ".join(logs)[:160],
            )
        else:
            check("fit skipped (no Gui)", True, "; ".join(logs)[:120])

        # --- fillet (confirm + Apply) ---
        resp = client.send_chat(
            {
                "app": "freecad",
                "version": config.CLIENT_VERSION,
                "context": ctx,
                "message": "Add a 2mm fillet to the selected box",
                "mode": "chat",
            }
        )
        tools = _tool_names(resp)
        check(
            "chat fillet -> add_fillet",
            "add_fillet" in tools,
            f"tools={tools} reply={(resp.get('reply_text') or '')[:60]}",
        )
        check("chat fillet need_confirm", _has_need_confirm(resp), "meta need_confirm")
        logs, pending = prepare_actions(resp, client=client, defer_confirm=True)
        check(
            "fillet deferred (Apply)",
            len(pending) == 1 and pending[0].tool_name == "add_fillet",
            f"logs={logs} pending={pending}",
        )
        # Simulate dock Cancel: nothing applied yet
        before = [o.Name for o in doc.Objects]
        check("pre-Apply no fillet obj", all("Fillet" not in n for n in before), str(before))

        # Ensure object_name for headless / selection-less runners
        for item in pending:
            if item.tool_name == "add_fillet" and not item.args.get("object_name"):
                item.args["object_name"] = "SoakBox"

        apply_logs = apply_pending(pending, client=client)
        after = [o.Name for o in doc.Objects]
        check(
            "Apply fillet",
            any("ok: add_fillet" in line for line in apply_logs)
            and any("Fillet" in n for n in after),
            f"logs={apply_logs} objects={after}",
        )
    except Exception as exc:
        check("soak body", False, str(exc))
        traceback.print_exc()
    finally:
        try:
            FreeCAD.closeDocument(doc.Name)
        except Exception:
            pass

    summary = f"summary: {PASS} pass / {FAIL} fail"
    print(summary, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write(summary + "\n")
    except Exception:
        pass
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
